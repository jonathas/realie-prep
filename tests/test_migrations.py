import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INITIAL_MIGRATION = ROOT / "migrations" / "versions" / "20260823_0001_initial.py"
DOMAIN_TABLES = {
    "answer_attempts",
    "categories",
    "question_options",
    "question_views",
    "questions",
    "quiz_batches",
    "quiz_sessions",
    "source_documents",
}


def run_alembic(database: Path, *arguments: str) -> None:
    environment = os.environ | {"DATABASE_URL": f"sqlite:///{database}"}
    subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


def table_names(database: Path) -> set[str]:
    with sqlite3.connect(database) as connection:
        return {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }


def test_initial_migration_is_explicit_and_reversible(tmp_path: Path) -> None:
    assert "create_all" not in INITIAL_MIGRATION.read_text(encoding="utf-8")
    database = tmp_path / "migration.db"

    run_alembic(database, "upgrade", "head")
    assert DOMAIN_TABLES <= table_names(database)
    run_alembic(database, "check")

    run_alembic(database, "downgrade", "base")
    assert DOMAIN_TABLES.isdisjoint(table_names(database))
