import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import AnswerAttempt, Question, QuestionView
from app.schemas import AnswerIn, NewBatchIn, SelectionMode, SubmitBatchIn
from app.services.quiz_service import QuestionSelectionService, QuizError, QuizService


def submit_with_wrong_views(
    service: QuizService, batch_id: int, view_ids: list[int], wrong_ids: set[int]
) -> None:
    service.submit(
        batch_id,
        SubmitBatchIn(
            answers=[
                AnswerIn(
                    question_view_id=view_id,
                    selected_option="B" if view_id in wrong_ids else "A",
                )
                for view_id in view_ids
            ]
        ),
    )


def test_unseen_batches_do_not_overlap(
    db: Session, settings: Settings, question_bank: object
) -> None:
    service = QuizService(db, settings)
    first = service.get_or_create_current().batches[0]
    assert all(question.selected_option is None for question in first.questions)
    assert first.score is None
    first_question_ids = {
        view.question_id
        for view in db.scalars(select(QuestionView).where(QuestionView.quiz_batch_id == first.id))
    }
    service.submit(
        first.id,
        SubmitBatchIn(
            answers=[AnswerIn(question_view_id=q.id, selected_option="A") for q in first.questions]
        ),
    )
    second = service.new_batch(NewBatchIn())
    second_question_ids = {
        view.question_id
        for view in db.scalars(select(QuestionView).where(QuestionView.quiz_batch_id == second.id))
    }
    assert len(first_question_ids) == len(second_question_ids) == 10
    assert first_question_ids.isdisjoint(second_question_ids)


def test_grading_persists_every_answer(
    db: Session, settings: Settings, question_bank: object
) -> None:
    service = QuizService(db, settings)
    batch = service.get_or_create_current().batches[0]
    submission = SubmitBatchIn(
        answers=[
            AnswerIn(question_view_id=question.id, selected_option="A" if index < 8 else "B")
            for index, question in enumerate(batch.questions)
        ]
    )
    result = service.submit(batch.id, submission)
    assert (result.score, result.total, result.accuracy) == (8, 10, 80.0)
    assert len(list(db.scalars(select(AnswerAttempt)))) == 10

    restored = service.get_or_create_current().batches[0]
    assert restored.submitted is True
    assert restored.score == 8
    assert restored.accuracy == 80.0
    assert [question.selected_option for question in restored.questions] == ["A"] * 8 + ["B"] * 2
    assert [question.correct for question in restored.questions] == [True] * 8 + [False] * 2
    assert all(question.correct_option == "A" for question in restored.questions)


def test_exhaustion_starts_review_only_after_every_question_was_seen(
    db: Session, settings: Settings, question_bank: object
) -> None:
    service = QuizService(db, settings)
    first = service.get_or_create_current().batches[0]
    submit_with_wrong_views(service, first.id, [q.id for q in first.questions], set())
    second = service.new_batch(NewBatchIn())
    submit_with_wrong_views(service, second.id, [q.id for q in second.questions], set())

    assert db.scalar(select(QuestionView).where(QuestionView.was_repeat.is_(True))) is None
    assert len(set(db.scalars(select(QuestionView.question_id)))) == 20

    third = service.new_batch(NewBatchIn())
    repeat_flags = list(
        db.scalars(
            select(QuestionView.was_repeat).where(QuestionView.quiz_batch_id == third.id)
        )
    )
    assert len(third.questions) == 10
    assert repeat_flags == [True] * 10


def test_exhausted_default_selection_skips_questions_in_current_session(
    db: Session, settings: Settings, question_bank: object
) -> None:
    service = QuizService(db, settings)
    first = service.get_or_create_current().batches[0]
    submit_with_wrong_views(service, first.id, [q.id for q in first.questions], set())
    second = service.new_batch(NewBatchIn())
    submit_with_wrong_views(service, second.id, [q.id for q in second.questions], set())

    first_ids = {question.question_id for question in first.questions}
    selected = service.selector.select_ids(
        10, allow_repeats=False, mode=SelectionMode.UNSEEN, excluded=first_ids
    )
    assert set(selected).isdisjoint(first_ids)


def test_intentional_review_repeats_an_incorrect_question_before_exhaustion(
    db: Session, settings: Settings, question_bank: object
) -> None:
    service = QuizService(db, settings)
    first = service.get_or_create_current().batches[0]
    target = first.questions[0]
    submit_with_wrong_views(
        service,
        first.id,
        [question.id for question in first.questions],
        {target.id},
    )

    review = service.new_batch(
        NewBatchIn(allow_repeats=True, mode=SelectionMode.INCORRECT)
    )
    repeated = next(
        question for question in review.questions if question.question_id == target.question_id
    )
    view = db.get(QuestionView, repeated.id)
    assert view is not None
    assert view.was_repeat is True
    assert len({question.question_id for question in review.questions}) == len(review.questions)


def test_missed_twice_is_prioritized_without_join_overcounting(
    db: Session, settings: Settings, question_bank: object
) -> None:
    service = QuizService(db, settings)
    first = service.get_or_create_current().batches[0]
    target = first.questions[0]
    submit_with_wrong_views(
        service,
        first.id,
        [question.id for question in first.questions],
        {target.id},
    )

    assert service.selector._review_ids(10, SelectionMode.MISSED_TWICE) == []
    second = service.new_batch(
        NewBatchIn(allow_repeats=True, mode=SelectionMode.INCORRECT)
    )
    target_view = next(q.id for q in second.questions if q.question_id == target.question_id)
    submit_with_wrong_views(
        service,
        second.id,
        [question.id for question in second.questions],
        {target_view},
    )

    selected = service.selector._review_ids(10, SelectionMode.MISSED_TWICE)
    assert selected == [target.question_id]
    assert service.selector._review_ids(10, SelectionMode.MIXED)[0] == target.question_id


def test_weak_topic_mode_excludes_categories_below_minimum_sample(
    db: Session, settings: Settings, question_bank: object
) -> None:
    service = QuizService(db, settings)
    first = service.get_or_create_current().batches[0]
    submit_with_wrong_views(
        service,
        first.id,
        [question.id for question in first.questions],
        set(),
    )
    eligible_category_ids = set(
        db.scalars(
            select(Question.category_id)
            .join(AnswerAttempt, AnswerAttempt.question_id == Question.id)
            .group_by(Question.category_id)
            .having(func.count(AnswerAttempt.id) >= settings.weak_topic_min_attempts)
        )
    )
    assert eligible_category_ids

    selected = QuestionSelectionService(db, settings).select_ids(
        10, True, SelectionMode.WEAK_TOPICS
    )
    categories = set(db.scalars(select(Question.category_id).where(Question.id.in_(selected))))
    assert categories <= eligible_category_ids


def test_duplicate_answer_entry_is_rejected(
    db: Session, settings: Settings, question_bank: object
) -> None:
    service = QuizService(db, settings)
    batch = service.get_or_create_current().batches[0]
    answers = [AnswerIn(question_view_id=q.id, selected_option="A") for q in batch.questions]
    with pytest.raises(QuizError, match="exactly once"):
        service.submit(batch.id, SubmitBatchIn(answers=answers + [answers[0]]))
