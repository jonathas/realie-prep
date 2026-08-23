from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class ValidationStatus(StrEnum):
    PENDING = "pending"
    VALID = "valid"
    IMPORTED = "imported"
    FAILED = "failed"


class MistakeType(StrEnum):
    VOCABULARY = "vocabulary"
    KNOWLEDGE = "knowledge"
    CARELESS = "careless"
    UNKNOWN = "unknown"


class SourceDocument(Base):
    __tablename__ = "source_documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(String(500))
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    question_count: Mapped[int] = mapped_column(default=0)
    category_count: Mapped[int] = mapped_column(default=0)
    validation_status: Mapped[ValidationStatus] = mapped_column(
        Enum(ValidationStatus), default=ValidationStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    questions: Mapped[list[Question]] = relationship(back_populates="source_document")


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (CheckConstraint("length(name) > 0"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[int | None] = mapped_column(Integer, unique=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    questions: Mapped[list[Question]] = relationship(back_populates="category")


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint("correct_option IN ('A', 'B', 'C', 'D')"),
        CheckConstraint("length(text) > 0"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id"))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    source_question_number: Mapped[int]
    official_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    source_updated_on: Mapped[date | None] = mapped_column(Date)
    stable_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    text: Mapped[str] = mapped_column(Text)
    correct_option: Mapped[str] = mapped_column(String(1))
    source_page: Mapped[int | None]
    image_path: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    source_document: Mapped[SourceDocument] = relationship(back_populates="questions")
    category: Mapped[Category] = relationship(back_populates="questions")
    options: Mapped[list[QuestionOption]] = relationship(
        back_populates="question", cascade="all, delete-orphan", order_by="QuestionOption.label"
    )
    views: Mapped[list[QuestionView]] = relationship(back_populates="question")
    attempts: Mapped[list[AnswerAttempt]] = relationship(back_populates="question")


class QuestionOption(Base):
    __tablename__ = "question_options"
    __table_args__ = (
        UniqueConstraint("question_id", "label"),
        CheckConstraint("label IN ('A', 'B', 'C', 'D')"),
        CheckConstraint("length(text) > 0"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(String(1))
    text: Mapped[str] = mapped_column(Text)
    image_path: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    question: Mapped[Question] = relationship(back_populates="options")


class QuizSession(Base):
    __tablename__ = "quiz_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    batches: Mapped[list[QuizBatch]] = relationship(back_populates="session")
    attempts: Mapped[list[AnswerAttempt]] = relationship(back_populates="session")


class QuizBatch(Base):
    __tablename__ = "quiz_batches"
    __table_args__ = (UniqueConstraint("quiz_session_id", "batch_number"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    quiz_session_id: Mapped[int] = mapped_column(ForeignKey("quiz_sessions.id"))
    batch_number: Mapped[int]
    allow_repeats: Mapped[bool] = mapped_column(Boolean, default=False)
    selection_mode: Mapped[str] = mapped_column(String(32), default="unseen")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    session: Mapped[QuizSession] = relationship(back_populates="batches")
    views: Mapped[list[QuestionView]] = relationship(
        back_populates="batch", cascade="all, delete-orphan", order_by="QuestionView.id"
    )


class QuestionView(Base):
    __tablename__ = "question_views"
    __table_args__ = (UniqueConstraint("question_id", "quiz_batch_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    quiz_batch_id: Mapped[int] = mapped_column(ForeignKey("quiz_batches.id"))
    shown_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    was_repeat: Mapped[bool] = mapped_column(Boolean, default=False)
    question: Mapped[Question] = relationship(back_populates="views")
    batch: Mapped[QuizBatch] = relationship(back_populates="views")
    attempt: Mapped[AnswerAttempt | None] = relationship(back_populates="question_view")


class AnswerAttempt(Base):
    __tablename__ = "answer_attempts"
    __table_args__ = (
        CheckConstraint("selected_option IN ('A', 'B', 'C', 'D')"),
        UniqueConstraint("question_view_id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    quiz_session_id: Mapped[int] = mapped_column(ForeignKey("quiz_sessions.id"))
    question_view_id: Mapped[int] = mapped_column(ForeignKey("question_views.id"))
    selected_option: Mapped[str] = mapped_column(String(1))
    correct: Mapped[bool] = mapped_column(Boolean)
    mistake_type: Mapped[MistakeType | None] = mapped_column(Enum(MistakeType))
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    question: Mapped[Question] = relationship(back_populates="attempts")
    session: Mapped[QuizSession] = relationship(back_populates="attempts")
    question_view: Mapped[QuestionView] = relationship(back_populates="attempt")
