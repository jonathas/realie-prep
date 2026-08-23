"""Initial schema."""

from collections.abc import Sequence

from alembic import op

revision: str = "20260823_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Keeping the migration generated from ORM metadata reduces drift in this initial schema.
    import app.models  # noqa: F401
    from app.database import Base

    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    import app.models  # noqa: F401
    from app.database import Base

    Base.metadata.drop_all(bind=op.get_bind())
