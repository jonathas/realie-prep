from sqlalchemy.orm import Session

from app.config import Settings
from app.schemas import AnswerIn, NewBatchIn, SubmitBatchIn
from app.services.quiz_service import QuizService
from app.services.statistics_service import StatisticsService


def test_accuracy_first_attempt_and_coverage(
    db: Session, settings: Settings, question_bank: object
) -> None:
    quiz = QuizService(db, settings)
    batch = quiz.get_or_create_current().batches[0]
    quiz.submit(
        batch.id,
        SubmitBatchIn(
            answers=[
                AnswerIn(question_view_id=question.id, selected_option="A" if index < 6 else "B")
                for index, question in enumerate(batch.questions)
            ]
        ),
    )
    stats = StatisticsService(db, settings).calculate()
    assert stats["overall_accuracy"] == 60.0
    assert stats["first_attempt_accuracy"] == 60.0
    assert stats["coverage_percent"] == 50.0
    assert stats["passing_difference"] == 0.0


def test_zero_attempt_state(db: Session, settings: Settings, question_bank: object) -> None:
    stats = StatisticsService(db, settings).calculate()
    assert stats["overall_accuracy"] == 0
    assert stats["first_attempt_accuracy"] == 0.0
    assert stats["unique_seen"] == 0


def test_recent_accuracy_reflects_review_rounds_after_first_attempts(
    db: Session, settings: Settings, question_bank: object
) -> None:
    quiz = QuizService(db, settings)
    first = quiz.get_or_create_current().batches[0]
    quiz.submit(
        first.id,
        SubmitBatchIn(
            answers=[
                AnswerIn(question_view_id=question.id, selected_option="B")
                for question in first.questions
            ]
        ),
    )
    second = quiz.new_batch(NewBatchIn())
    quiz.submit(
        second.id,
        SubmitBatchIn(
            answers=[
                AnswerIn(question_view_id=question.id, selected_option="A")
                for question in second.questions
            ]
        ),
    )
    third = quiz.new_batch(NewBatchIn())
    quiz.submit(
        third.id,
        SubmitBatchIn(
            answers=[
                AnswerIn(question_view_id=question.id, selected_option="A")
                for question in third.questions
            ]
        ),
    )

    stats = StatisticsService(db, settings).calculate()
    assert stats["first_attempt_accuracy"] == 50.0
    assert stats["recent_accuracy"] == 66.7
    assert stats["passing_difference"] == 6.7
