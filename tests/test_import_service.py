from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Question
from app.schemas import ExtractedOption, ExtractedQuestion, ExtractedQuestionBank
from app.services.import_service import ImportService


def make_bank(count: int = 20) -> ExtractedQuestionBank:
    return ExtractedQuestionBank(
        questions=[
            ExtractedQuestion(
                category=f"Topic {(index // 10) + 1}",
                category_number=(index // 10) + 1,
                question_number=(index % 10) + 1,
                text=f"Question {index + 1}",
                options=[ExtractedOption(label=label, text=f"Option {label}") for label in "ABCD"],
                correct_answer="A",
            )
            for index in range(count)
        ]
    )


def test_valid_bank_imports_transactionally(db: Session, settings: Settings) -> None:
    service = ImportService(db, settings)
    bank = make_bank()
    assert service.validate(bank) == []
    pending = service.save_pending(
        "Official test bank",
        "b" * 64,
        bank,
        source_url="https://example.test/questions",
    )
    service.confirm(pending.token)
    assert db.scalar(select(func.count(Question.id))) == 20


def test_wrong_count_and_duplicate_ids_are_rejected(db: Session, settings: Settings) -> None:
    service = ImportService(db, settings)
    short = make_bank(19)
    assert any("Expected 20" in error for error in service.validate(short))
    duplicate = make_bank()
    duplicate.questions[-1] = duplicate.questions[0].model_copy()
    assert "Duplicate stable question IDs exist" in service.validate(duplicate)
