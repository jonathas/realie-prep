from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from sqlalchemy import Engine, create_engine, event, func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import Base
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
from app.schemas import AnswerIn, SubmitBatchIn
from app.services.quiz_service import QuizError, QuizService


@pytest.fixture
def concurrent_engine(tmp_path: Path) -> Generator[Engine, None, None]:
    database = tmp_path / "concurrency.db"
    engine = create_engine(
        f"sqlite:///{database}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        source = SourceDocument(
            filename="Concurrency test bank",
            source_url="https://example.test/questions",
            sha256="c" * 64,
            question_count=20,
            category_count=2,
            validation_status=ValidationStatus.IMPORTED,
        )
        db.add(source)
        db.flush()
        for category_number in range(1, 3):
            category = Category(number=category_number, name=f"Topic {category_number}")
            db.add(category)
            db.flush()
            for question_number in range(1, 11):
                question = Question(
                    source_document_id=source.id,
                    category_id=category.id,
                    source_question_number=question_number,
                    stable_key=f"{category_number}.{question_number}",
                    text=f"Question {category_number}.{question_number}?",
                    correct_option="A",
                )
                db.add(question)
                db.flush()
                db.add_all(
                    QuestionOption(question_id=question.id, label=label, text=f"Option {label}")
                    for label in "ABCD"
                )
        db.commit()
    yield engine
    engine.dispose()


def synchronize_first_flush(db: Session, barrier: Barrier) -> None:
    def wait_before_flush(
        session: Session, flush_context: object, instances: object
    ) -> None:
        barrier.wait(timeout=10)

    event.listen(db, "before_flush", wait_before_flush, once=True)


def test_concurrent_first_load_reuses_one_session_and_batch(
    concurrent_engine: Engine, settings: Settings
) -> None:
    barrier = Barrier(2)

    def load_today() -> tuple[int, int]:
        with Session(concurrent_engine, expire_on_commit=False) as db:
            synchronize_first_flush(db, barrier)
            current = QuizService(db, settings).get_or_create_current()
            return current.id, current.batches[0].id

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: load_today(), range(2)))

    assert results[0] == results[1]
    with Session(concurrent_engine) as db:
        assert db.scalar(select(func.count(QuizSession.id))) == 1
        assert db.scalar(select(func.count(QuizBatch.id))) == 1
        assert db.scalar(select(func.count(QuestionView.id))) == 10
        assert db.scalar(select(func.count(func.distinct(QuestionView.question_id)))) == 10


def test_concurrent_submission_is_saved_once_and_fails_cleanly(
    concurrent_engine: Engine, settings: Settings
) -> None:
    with Session(concurrent_engine, expire_on_commit=False) as db:
        batch = QuizService(db, settings).get_or_create_current().batches[0]
        batch_id = batch.id
        submission = SubmitBatchIn(
            answers=[AnswerIn(question_view_id=q.id, selected_option="A") for q in batch.questions]
        )

    barrier = Barrier(2)

    def submit() -> str:
        with Session(concurrent_engine, expire_on_commit=False) as db:
            synchronize_first_flush(db, barrier)
            try:
                QuizService(db, settings).submit(batch_id, submission)
            except QuizError as exc:
                return str(exc)
            return "saved"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: submit(), range(2)))

    assert results.count("saved") == 1
    assert len([result for result in results if "already submitted" in result]) == 1
    with Session(concurrent_engine) as db:
        assert db.scalar(select(func.count(AnswerAttempt.id))) == 10
