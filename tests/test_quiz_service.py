from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import AnswerAttempt, QuestionView
from app.schemas import AnswerIn, NewBatchIn, SubmitBatchIn
from app.services.quiz_service import QuizService


def test_unseen_batches_do_not_overlap(
    db: Session, settings: Settings, question_bank: object
) -> None:
    service = QuizService(db, settings)
    first = service.get_or_create_current().batches[0]
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
