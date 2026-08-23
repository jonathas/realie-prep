import hashlib
import json
import shutil
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import (
    AnswerAttempt,
    Category,
    Question,
    QuestionOption,
    QuestionView,
    QuizBatch,
    QuizSession,
    SourceDocument,
    ValidationStatus,
)
from app.schemas import ExtractedQuestionBank, ImportPreviewOut


class ImportValidationError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


@dataclass(frozen=True)
class PendingImport:
    token: str
    filename: str
    sha256: str
    source_url: str | None
    bank: ExtractedQuestionBank


class ImportService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    @staticmethod
    def digest(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def validate(self, bank: ExtractedQuestionBank) -> list[str]:
        errors: list[str] = []
        if len(bank.questions) != self.settings.expected_question_count:
            errors.append(
                f"Expected {self.settings.expected_question_count} questions, "
                f"found {len(bank.questions)}"
            )
        stable_keys = [question.stable_key for question in bank.questions]
        if len(stable_keys) != len(set(stable_keys)):
            errors.append("Duplicate stable question IDs exist")
        categories = {(q.category_number, q.category) for q in bank.questions}
        if len(categories) != self.settings.expected_category_count:
            expected = self.settings.expected_category_count
            errors.append(f"Expected {expected} categories, found {len(categories)}")
        if self.settings.expected_questions_per_category:
            counts: dict[tuple[int | None, str], int] = {}
            for question in bank.questions:
                key = (question.category_number, question.category)
                counts[key] = counts.get(key, 0) + 1
            malformed = [
                name
                for (_, name), count in counts.items()
                if count != self.settings.expected_questions_per_category
            ]
            if malformed:
                errors.append(
                    "Categories with unexpected question counts: " + ", ".join(sorted(malformed))
                )
        return errors

    def ensure_new_hash(self, sha256: str) -> None:
        existing = self.db.scalar(
            select(SourceDocument).where(
                SourceDocument.sha256 == sha256,
                SourceDocument.validation_status == ValidationStatus.IMPORTED,
            )
        )
        if existing:
            raise ImportValidationError(["The official question bank is already up to date"])

    def save_pending(
        self,
        filename: str,
        sha256: str,
        bank: ExtractedQuestionBank,
        source_url: str | None = None,
        assets: dict[str, bytes] | None = None,
    ) -> PendingImport:
        token = uuid.uuid4().hex
        self.settings.upload_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "filename": filename,
            "sha256": sha256,
            "source_url": source_url,
            "bank": bank.model_dump(mode="json"),
        }
        (self.settings.upload_dir / f"{token}.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
        if assets:
            asset_dir = self.settings.upload_dir / token
            asset_dir.mkdir()
            for name, content in assets.items():
                (asset_dir / name).write_bytes(content)
        return PendingImport(token, filename, sha256, source_url, bank)

    def load_pending(self, token: str) -> PendingImport:
        if not token.isalnum():
            raise ImportValidationError(["Invalid preview token"])
        path = self.settings.upload_dir / f"{token}.json"
        if not path.exists():
            raise ImportValidationError(["Import preview expired or does not exist"])
        payload = json.loads(path.read_text(encoding="utf-8"))
        return PendingImport(
            token=token,
            filename=payload["filename"],
            sha256=payload["sha256"],
            source_url=payload.get("source_url"),
            bank=ExtractedQuestionBank.model_validate_json(
                json.dumps(payload["bank"]), strict=True
            ),
        )

    def preview(self, pending: PendingImport) -> ImportPreviewOut:
        errors = self.validate(pending.bank)
        return ImportPreviewOut(
            token=pending.token,
            filename=pending.filename,
            sha256=pending.sha256,
            question_count=len(pending.bank.questions),
            category_count=len({(q.category_number, q.category) for q in pending.bank.questions}),
            option_count=sum(len(q.options) for q in pending.bank.questions),
            valid=not errors,
            errors=errors,
        )

    def confirm(self, token: str) -> SourceDocument:
        pending = self.load_pending(token)
        errors = self.validate(pending.bank)
        if errors:
            raise ImportValidationError(errors)
        self.ensure_new_hash(pending.sha256)
        try:
            # Re-import replaces the active bank and progress atomically.
            for model in (
                AnswerAttempt,
                QuestionView,
                QuizBatch,
                QuizSession,
                QuestionOption,
                Question,
                Category,
                SourceDocument,
            ):
                self.db.execute(delete(model))
            source = SourceDocument(
                filename=pending.filename,
                source_url=pending.source_url,
                sha256=pending.sha256,
                imported_at=datetime.now(UTC),
                question_count=len(pending.bank.questions),
                category_count=len({q.category for q in pending.bank.questions}),
                validation_status=ValidationStatus.IMPORTED,
            )
            self.db.add(source)
            self.db.flush()
            categories: dict[tuple[int | None, str], Category] = {}
            for extracted in pending.bank.questions:
                category_key = (extracted.category_number, extracted.category)
                category = categories.get(category_key)
                if category is None:
                    category = Category(number=extracted.category_number, name=extracted.category)
                    self.db.add(category)
                    self.db.flush()
                    categories[category_key] = category
                question = Question(
                    source_document_id=source.id,
                    category_id=category.id,
                    source_question_number=extracted.question_number,
                    official_id=extracted.official_id,
                    source_updated_on=extracted.source_updated_on,
                    stable_key=extracted.stable_key,
                    text=extracted.text,
                    correct_option=extracted.correct_answer,
                    source_page=extracted.source_page,
                    image_path=extracted.image_path,
                )
                self.db.add(question)
                self.db.flush()
                self.db.add_all(
                    QuestionOption(
                        question_id=question.id,
                        label=o.label,
                        text=o.text,
                        image_path=o.image_path,
                    )
                    for o in extracted.options
                )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        (self.settings.upload_dir / f"{token}.json").unlink(missing_ok=True)
        pending_assets = self.settings.upload_dir / token
        if pending_assets.exists():
            destination = self.settings.upload_dir.parent / "question-images"
            destination.mkdir(parents=True, exist_ok=True)
            for asset in pending_assets.iterdir():
                shutil.copy2(asset, destination / asset.name)
            shutil.rmtree(pending_assets)
        return source
