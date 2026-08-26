"""Initial schema."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260823_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

validation_status = sa.Enum(
    "PENDING", "VALID", "IMPORTED", "FAILED", name="validationstatus"
)
mistake_type = sa.Enum(
    "VOCABULARY", "KNOWLEDGE", "CARELESS", "UNKNOWN", name="mistaketype"
)


def upgrade() -> None:
    op.create_table(
        "source_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("category_count", sa.Integer(), nullable=False),
        sa.Column("validation_status", validation_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_source_documents_sha256"), "source_documents", ["sha256"], unique=True
    )

    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(name) > 0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("number"),
    )

    op.create_table(
        "quiz_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_quiz_sessions_session_date"),
        "quiz_sessions",
        ["session_date"],
        unique=True,
    )

    op.create_table(
        "questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_document_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("source_question_number", sa.Integer(), nullable=False),
        sa.Column("official_id", sa.String(length=64), nullable=True),
        sa.Column("source_updated_on", sa.Date(), nullable=True),
        sa.Column("stable_key", sa.String(length=64), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("correct_option", sa.String(length=1), nullable=False),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("image_path", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("correct_option IN ('A', 'B', 'C', 'D')"),
        sa.CheckConstraint("length(text) > 0"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("official_id"),
    )
    op.create_index(op.f("ix_questions_category_id"), "questions", ["category_id"])
    op.create_index(
        op.f("ix_questions_stable_key"), "questions", ["stable_key"], unique=True
    )

    op.create_table(
        "question_options",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=1), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("image_path", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("label IN ('A', 'B', 'C', 'D')"),
        sa.CheckConstraint("length(text) > 0"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("question_id", "label"),
    )

    op.create_table(
        "quiz_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quiz_session_id", sa.Integer(), nullable=False),
        sa.Column("batch_number", sa.Integer(), nullable=False),
        sa.Column("allow_repeats", sa.Boolean(), nullable=False),
        sa.Column("selection_mode", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["quiz_session_id"], ["quiz_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("quiz_session_id", "batch_number"),
    )

    op.create_table(
        "question_views",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("quiz_batch_id", sa.Integer(), nullable=False),
        sa.Column("shown_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("was_repeat", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"]),
        sa.ForeignKeyConstraint(["quiz_batch_id"], ["quiz_batches.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("question_id", "quiz_batch_id"),
    )
    op.create_index(
        op.f("ix_question_views_question_id"), "question_views", ["question_id"]
    )

    op.create_table(
        "answer_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("quiz_session_id", sa.Integer(), nullable=False),
        sa.Column("question_view_id", sa.Integer(), nullable=False),
        sa.Column("selected_option", sa.String(length=1), nullable=False),
        sa.Column("correct", sa.Boolean(), nullable=False),
        sa.Column("mistake_type", mistake_type, nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("selected_option IN ('A', 'B', 'C', 'D')"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"]),
        sa.ForeignKeyConstraint(["question_view_id"], ["question_views.id"]),
        sa.ForeignKeyConstraint(["quiz_session_id"], ["quiz_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("question_view_id"),
    )
    op.create_index(
        op.f("ix_answer_attempts_question_id"), "answer_attempts", ["question_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_answer_attempts_question_id"), table_name="answer_attempts")
    op.drop_table("answer_attempts")
    op.drop_index(op.f("ix_question_views_question_id"), table_name="question_views")
    op.drop_table("question_views")
    op.drop_table("quiz_batches")
    op.drop_table("question_options")
    op.drop_index(op.f("ix_questions_stable_key"), table_name="questions")
    op.drop_index(op.f("ix_questions_category_id"), table_name="questions")
    op.drop_table("questions")
    op.drop_index(op.f("ix_quiz_sessions_session_date"), table_name="quiz_sessions")
    op.drop_table("quiz_sessions")
    op.drop_table("categories")
    op.drop_index(op.f("ix_source_documents_sha256"), table_name="source_documents")
    op.drop_table("source_documents")
    mistake_type.drop(op.get_bind(), checkfirst=True)
    validation_status.drop(op.get_bind(), checkfirst=True)
