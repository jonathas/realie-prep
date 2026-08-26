from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.config import Settings
from app.models import (
    AnswerAttempt,
    Category,
    MistakeType,
    Question,
    QuestionView,
    QuizBatch,
    QuizSession,
    utcnow,
)
from app.schemas import (
    AnswerResult,
    BatchOut,
    BatchResult,
    NewBatchIn,
    OptionOut,
    QuestionOut,
    SelectionMode,
    SessionOut,
    SubmitBatchIn,
)


class QuizError(ValueError):
    pass


class ConcurrentQuizError(QuizError):
    pass


def current_study_date(settings: Settings, instant: datetime | None = None) -> date:
    current = instant or datetime.now(UTC)
    if current.tzinfo is None:
        raise ValueError("Study-date calculation requires a timezone-aware datetime")
    return current.astimezone(ZoneInfo(settings.app_timezone)).date()


class QuestionSelectionService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    def _unseen_ids(self, limit: int) -> list[int]:
        viewed = select(QuestionView.question_id)
        return list(
            self.db.scalars(
                select(Question.id)
                .where(Question.id.not_in(viewed))
                .order_by(func.random())
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )

    def _review_ids(self, limit: int, mode: SelectionMode) -> list[int]:
        incorrect_count = (
            select(func.count(AnswerAttempt.id))
            .where(
                AnswerAttempt.question_id == Question.id,
                AnswerAttempt.correct.is_(False),
            )
            .correlate(Question)
            .scalar_subquery()
        )
        last_seen = (
            select(func.max(QuestionView.shown_at))
            .where(QuestionView.question_id == Question.id)
            .correlate(Question)
            .scalar_subquery()
        )
        weak_categories = (
            select(Category.id)
            .join(Question, Question.category_id == Category.id)
            .join(AnswerAttempt, AnswerAttempt.question_id == Question.id)
            .group_by(Category.id)
            .having(func.count(AnswerAttempt.id) >= self.settings.weak_topic_min_attempts)
            .order_by(func.avg(case((AnswerAttempt.correct.is_(True), 1.0), else_=0.0)))
            .limit(3)
        )
        query = select(Question.id)
        if mode == SelectionMode.MISSED_TWICE:
            query = query.where(incorrect_count >= 2).order_by(incorrect_count.desc(), last_seen)
        elif mode == SelectionMode.INCORRECT:
            query = query.where(incorrect_count >= 1).order_by(incorrect_count.desc(), last_seen)
        elif mode == SelectionMode.WEAK_TOPICS:
            query = query.where(Question.category_id.in_(weak_categories)).order_by(last_seen)
        else:
            priority = case(
                (incorrect_count >= 2, 0),
                (Question.category_id.in_(weak_categories), 1),
                (incorrect_count >= 1, 2),
                else_=3,
            )
            query = query.order_by(priority, incorrect_count.desc(), last_seen)
        return list(self.db.scalars(query.limit(limit)))

    def select_ids(self, limit: int, allow_repeats: bool, mode: SelectionMode) -> list[int]:
        if mode == SelectionMode.UNSEEN and not allow_repeats:
            unseen = self._unseen_ids(limit)
            if len(unseen) == limit:
                return unseen
            review = [
                q for q in self._review_ids(limit * 2, SelectionMode.MIXED) if q not in unseen
            ]
            return unseen + review[: limit - len(unseen)]
        ids = self._review_ids(limit, mode if mode != SelectionMode.UNSEEN else SelectionMode.MIXED)
        if len(ids) < limit:
            existing = set(ids)
            ids.extend(
                self.db.scalars(
                    select(Question.id)
                    .where(Question.id.not_in(existing))
                    .order_by(func.random())
                    .limit(limit - len(ids))
                )
            )
        return ids


class QuizService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.selector = QuestionSelectionService(db, settings)

    def today(self) -> QuizSession:
        today = current_study_date(self.settings)
        session = self.db.scalar(select(QuizSession).where(QuizSession.session_date == today))
        if session is None:
            session = QuizSession(session_date=today)
            self.db.add(session)
            try:
                self.db.commit()
            except IntegrityError:
                self.db.rollback()
                session = self.db.scalar(
                    select(QuizSession).where(QuizSession.session_date == today)
                )
                if session is None:
                    raise
        return session

    def get_or_create_current(self) -> SessionOut:
        session = self.today()
        batches = list(
            self.db.scalars(
                select(QuizBatch)
                .where(QuizBatch.quiz_session_id == session.id)
                .order_by(QuizBatch.batch_number)
            )
        )
        if not batches and self.db.scalar(select(func.count(Question.id))):
            try:
                self.create_batch(session, NewBatchIn())
            except ConcurrentQuizError:
                self.db.expire_all()
        return self.serialize_session(session)

    def create_batch(self, session: QuizSession, request: NewBatchIn) -> QuizBatch:
        existing = list(
            self.db.scalars(
                select(QuizBatch)
                .where(QuizBatch.quiz_session_id == session.id)
                .order_by(QuizBatch.id)
            )
        )
        if existing and existing[-1].submitted_at is None:
            raise QuizError("Submit the current batch before requesting another one")
        batch = QuizBatch(
            quiz_session_id=session.id,
            batch_number=len(existing) + 1,
            allow_repeats=request.allow_repeats,
            selection_mode=request.mode.value,
        )
        try:
            self.db.add(batch)
            # Flush before selection to acquire SQLite's writer lock. PostgreSQL uses
            # row locking in the selector. The view records commit with this batch.
            self.db.flush()
            ids = self.selector.select_ids(10, request.allow_repeats, request.mode)
            if not ids:
                self.db.rollback()
                raise QuizError("No questions are available for this study mode")
            previously_seen = set(
                self.db.scalars(
                    select(QuestionView.question_id).where(QuestionView.question_id.in_(ids))
                )
            )
            self.db.add_all(
                QuestionView(
                    question_id=qid,
                    quiz_batch_id=batch.id,
                    was_repeat=qid in previously_seen,
                )
                for qid in ids
            )
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            concurrent_batch = self.db.scalar(
                select(QuizBatch).where(
                    QuizBatch.quiz_session_id == session.id,
                    QuizBatch.batch_number == batch.batch_number,
                )
            )
            if concurrent_batch is not None:
                raise ConcurrentQuizError(
                    "Another request already created the next batch"
                ) from exc
            raise
        return batch

    def new_batch(self, request: NewBatchIn) -> BatchOut:
        batch = self.create_batch(self.today(), request)
        return self.serialize_batch(batch)

    def submit(self, batch_id: int, submission: SubmitBatchIn) -> BatchResult:
        batch = self.db.get(QuizBatch, batch_id)
        if batch is None:
            raise QuizError("Batch not found")
        if batch.submitted_at is not None:
            raise QuizError("This batch was already submitted")
        views = list(
            self.db.scalars(
                select(QuestionView)
                .options(joinedload(QuestionView.question))
                .where(QuestionView.quiz_batch_id == batch_id)
            ).unique()
        )
        answers = {answer.question_view_id: answer.selected_option for answer in submission.answers}
        if len(answers) != len(submission.answers) or set(answers) != {view.id for view in views}:
            raise QuizError("Every question in the batch must be answered exactly once")
        results: list[AnswerResult] = []
        for view in views:
            selected = answers[view.id]
            correct = selected == view.question.correct_option
            self.db.add(
                AnswerAttempt(
                    question_id=view.question_id,
                    quiz_session_id=batch.quiz_session_id,
                    question_view_id=view.id,
                    selected_option=selected,
                    correct=correct,
                )
            )
            results.append(
                AnswerResult(
                    question_view_id=view.id,
                    question_id=view.question_id,
                    selected_option=selected,
                    correct_option=view.question.correct_option,
                    correct=correct,
                )
            )
        batch.submitted_at = utcnow()
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            persisted_batch = self.db.get(QuizBatch, batch_id)
            if persisted_batch is not None and persisted_batch.submitted_at is not None:
                raise ConcurrentQuizError("This batch was already submitted") from exc
            raise
        score = sum(result.correct for result in results)
        return BatchResult(
            score=score,
            total=len(results),
            accuracy=round(score / len(results) * 100, 1) if results else 0,
            results=results,
        )

    def classify(self, view_id: int, mistake_type: MistakeType) -> None:
        attempt = self.db.scalar(
            select(AnswerAttempt).where(AnswerAttempt.question_view_id == view_id)
        )
        if attempt is None or attempt.correct:
            raise QuizError("Only an incorrect answer can be classified")
        attempt.mistake_type = mistake_type
        self.db.commit()

    def serialize_session(self, session: QuizSession) -> SessionOut:
        batches = list(
            self.db.scalars(
                select(QuizBatch)
                .where(QuizBatch.quiz_session_id == session.id)
                .order_by(QuizBatch.batch_number)
            )
        )
        return SessionOut(
            id=session.id,
            date=session.session_date.isoformat(),
            batches=[self.serialize_batch(batch) for batch in batches],
            bank_empty=not bool(self.db.scalar(select(func.count(Question.id)))),
        )

    def serialize_batch(self, batch: QuizBatch) -> BatchOut:
        views = list(
            self.db.scalars(
                select(QuestionView)
                .options(
                    joinedload(QuestionView.question).joinedload(Question.options),
                    joinedload(QuestionView.question).joinedload(Question.category),
                    joinedload(QuestionView.attempt),
                )
                .where(QuestionView.quiz_batch_id == batch.id)
                .order_by(QuestionView.id)
            ).unique()
        )
        attempts = [view.attempt for view in views if view.attempt is not None]
        score = sum(attempt.correct for attempt in attempts)
        return BatchOut(
            id=batch.id,
            batch_number=batch.batch_number,
            submitted=batch.submitted_at is not None,
            allow_repeats=batch.allow_repeats,
            selection_mode=batch.selection_mode,
            questions=[
                QuestionOut(
                    id=view.id,
                    question_id=view.question_id,
                    stable_key=view.question.stable_key,
                    category=view.question.category.name,
                    text=view.question.text,
                    image_path=view.question.image_path,
                    options=[
                        OptionOut(label=o.label, text=o.text, image_path=o.image_path)
                        for o in view.question.options
                    ],
                    selected_option=view.attempt.selected_option if view.attempt else None,
                    correct_option=view.question.correct_option if view.attempt else None,
                    correct=view.attempt.correct if view.attempt else None,
                    mistake_type=view.attempt.mistake_type if view.attempt else None,
                )
                for view in views
            ],
            score=score if batch.submitted_at is not None else None,
            accuracy=(round(score / len(attempts) * 100, 1) if attempts else 0.0)
            if batch.submitted_at is not None
            else None,
        )
