import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Question, QuestionOption, SourceDocument
from app.schemas import ExtractedOption, ExtractedQuestion, ExtractedQuestionBank
from app.services.import_service import ImportService, ImportValidationError


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


def bank_with_images() -> ExtractedQuestionBank:
    bank = make_bank()
    bank.questions[0].image_path = "/question-images/1-1-prompt.jpg"
    bank.questions[0].options[0].image_path = "/question-images/1-1-a.jpg"
    return bank


def test_updated_images_use_immutable_bank_paths(
    db: Session, settings: Settings
) -> None:
    service = ImportService(db, settings)
    old_hash = "b" * 64
    old = service.save_pending(
        "Old bank",
        old_hash,
        bank_with_images(),
        assets={"1-1-prompt.jpg": b"old prompt", "1-1-a.jpg": b"old option"},
    )
    service.confirm(old.token)

    old_question = db.scalar(select(Question).where(Question.stable_key == "1.1"))
    old_option = db.scalar(
        select(QuestionOption).where(
            QuestionOption.question_id == old_question.id,
            QuestionOption.label == "A",
        )
    )
    assert old_question.image_path == f"/question-images/{old_hash}/1-1-prompt.jpg"
    assert old_option is not None
    assert old_option.image_path == f"/question-images/{old_hash}/1-1-a.jpg"

    new_hash = "c" * 64
    new = service.save_pending(
        "Updated bank",
        new_hash,
        bank_with_images(),
        assets={"1-1-prompt.jpg": b"new prompt", "1-1-a.jpg": b"new option"},
    )
    service.confirm(new.token)
    db.expire_all()

    updated = db.scalar(select(Question).where(Question.stable_key == "1.1"))
    assert updated.image_path == f"/question-images/{new_hash}/1-1-prompt.jpg"
    image_root = settings.upload_dir.parent / "question-images"
    assert (image_root / old_hash / "1-1-prompt.jpg").read_bytes() == b"old prompt"
    assert (image_root / new_hash / "1-1-prompt.jpg").read_bytes() == b"new prompt"


def test_failed_database_commit_restores_pending_images_and_active_bank(
    db: Session, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = ImportService(db, settings)
    old_hash = "b" * 64
    old = service.save_pending(
        "Old bank",
        old_hash,
        bank_with_images(),
        assets={"1-1-prompt.jpg": b"old prompt", "1-1-a.jpg": b"old option"},
    )
    service.confirm(old.token)

    new_hash = "c" * 64
    pending = service.save_pending(
        "Updated bank",
        new_hash,
        bank_with_images(),
        assets={"1-1-prompt.jpg": b"new prompt", "1-1-a.jpg": b"new option"},
    )

    def fail_commit() -> None:
        raise RuntimeError("simulated database failure")

    monkeypatch.setattr(db, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="simulated database failure"):
        service.confirm(pending.token)

    db.expire_all()
    active = db.scalar(select(SourceDocument))
    question = db.scalar(select(Question).where(Question.stable_key == "1.1"))
    assert active.sha256 == old_hash
    assert question.image_path == f"/question-images/{old_hash}/1-1-prompt.jpg"
    image_root = settings.upload_dir.parent / "question-images"
    assert not (image_root / new_hash).exists()
    assert (settings.upload_dir / pending.token / "1-1-prompt.jpg").read_bytes() == b"new prompt"


def test_missing_downloaded_image_rejects_confirmation_without_replacing_bank(
    db: Session, settings: Settings
) -> None:
    service = ImportService(db, settings)
    existing = service.save_pending("Old bank", "b" * 64, make_bank())
    service.confirm(existing.token)
    pending = service.save_pending(
        "Broken update",
        "c" * 64,
        bank_with_images(),
        assets={"1-1-prompt.jpg": b"prompt only"},
    )

    with pytest.raises(ImportValidationError, match="Downloaded images are incomplete"):
        service.confirm(pending.token)

    assert db.scalar(select(SourceDocument.sha256)) == "b" * 64
    assert db.scalar(select(func.count(Question.id))) == 20
