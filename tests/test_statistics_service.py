from sqlalchemy.orm import Session

from app.config import Settings
from app.schemas import AnswerIn, SubmitBatchIn
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
