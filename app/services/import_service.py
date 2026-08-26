import hashlib
import json
import os
import shutil
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

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

IMAGE_URL_PREFIX = "/question-images/"


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

    @staticmethod
    def _validate_sha256(sha256: str) -> None:
        if len(sha256) != 64 or any(character not in "0123456789abcdef" for character in sha256):
            raise ImportValidationError(["Invalid question-bank SHA-256 digest"])

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
        self._validate_sha256(sha256)
        if assets:
            invalid_names = [name for name in assets if Path(name).name != name]
            if invalid_names:
                raise ImportValidationError(
                    ["Invalid image filename: " + ", ".join(sorted(invalid_names))]
                )
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

    @staticmethod
    def _asset_filename(image_path: str) -> str:
        if not image_path.startswith(IMAGE_URL_PREFIX):
            raise ImportValidationError([f"Invalid question image path: {image_path}"])
        relative = image_path.removeprefix(IMAGE_URL_PREFIX)
        parsed = PurePosixPath(relative)
        if not relative or parsed.name != relative or relative in {".", ".."}:
            raise ImportValidationError([f"Invalid question image path: {image_path}"])
        return relative

    def _referenced_assets(self, bank: ExtractedQuestionBank) -> set[str]:
        paths = [question.image_path for question in bank.questions]
        paths.extend(
            option.image_path for question in bank.questions for option in question.options
        )
        return {self._asset_filename(path) for path in paths if path is not None}

    @staticmethod
    def _versioned_image_path(image_path: str | None, sha256: str) -> str | None:
        if image_path is None:
            return None
        filename = ImportService._asset_filename(image_path)
        return f"{IMAGE_URL_PREFIX}{sha256}/{filename}"

    @staticmethod
    def _generation_matches(generation: Path, pending_assets: Path) -> bool:
        generation_files = {path.name for path in generation.iterdir() if path.is_file()}
        pending_files = {path.name for path in pending_assets.iterdir() if path.is_file()}
        return generation_files == pending_files and all(
            (generation / name).read_bytes() == (pending_assets / name).read_bytes()
            for name in pending_files
        )

    def _promote_assets(self, pending: PendingImport) -> tuple[Path | None, bool]:
        pending_assets = self.settings.upload_dir / pending.token
        image_root = self.settings.upload_dir.parent / "question-images"
        required_assets = self._referenced_assets(pending.bank)
        available_assets = (
            {path.name for path in pending_assets.iterdir() if path.is_file()}
            if pending_assets.exists()
            else set()
        )
        missing = sorted(required_assets - available_assets)
        if missing:
            raise ImportValidationError(
                ["Downloaded images are incomplete: " + ", ".join(missing)]
            )
        if not available_assets:
            return None, False

        image_root.mkdir(parents=True, exist_ok=True)
        generation = image_root / pending.sha256
        if generation.exists():
            if generation.is_dir() and self._generation_matches(generation, pending_assets):
                return generation, False
            raise ImportValidationError(
                ["An image generation with this bank digest already exists but differs"]
            )
        try:
            os.rename(pending_assets, generation)
        except OSError:
            if generation.is_dir() and self._generation_matches(generation, pending_assets):
                return generation, False
            raise
        return generation, True

    def _restore_pending_assets(self, generation: Path | None, token: str) -> None:
        if generation is None or not generation.exists():
            return
        pending_assets = self.settings.upload_dir / token
        os.replace(generation, pending_assets)

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
        self._validate_sha256(pending.sha256)
        self.ensure_new_hash(pending.sha256)
        generation, owns_generation = self._promote_assets(pending)
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
                    image_path=self._versioned_image_path(
                        extracted.image_path, pending.sha256
                    ),
                )
                self.db.add(question)
                self.db.flush()
                self.db.add_all(
                    QuestionOption(
                        question_id=question.id,
                        label=o.label,
                        text=o.text,
                        image_path=self._versioned_image_path(o.image_path, pending.sha256),
                    )
                    for o in extracted.options
                )
            self.db.commit()
        except Exception:
            self.db.rollback()
            if owns_generation:
                self._restore_pending_assets(generation, token)
            raise
        (self.settings.upload_dir / f"{token}.json").unlink(missing_ok=True)
        pending_assets = self.settings.upload_dir / token
        if pending_assets.exists():
            shutil.rmtree(pending_assets)
        return source
