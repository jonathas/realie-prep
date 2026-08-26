from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api import router
from app.config import Settings, get_settings
from app.database import Base, get_db
from app.models import Category, Question, QuestionOption, SourceDocument, ValidationStatus


@pytest.fixture
def settings(tmp_path: object) -> Settings:
    return Settings(
        expected_question_count=20,
        expected_category_count=2,
        expected_questions_per_category=10,
        weak_topic_min_attempts=2,
        upload_dir=tmp_path,  # type: ignore[arg-type]
    )


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    Base.metadata.drop_all(engine)


@pytest.fixture
def client(db: Session, settings: Settings) -> Generator[TestClient, None, None]:
    app = FastAPI()
    app.include_router(router)

    def override_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def question_bank(db: Session) -> list[Question]:
    source = SourceDocument(
        filename="Official test bank",
        source_url="https://example.test/questions",
        sha256="a" * 64,
        question_count=20,
        category_count=2,
        validation_status=ValidationStatus.IMPORTED,
    )
    db.add(source)
    db.flush()
    questions: list[Question] = []
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
            questions.append(question)
    db.commit()
    return questions
