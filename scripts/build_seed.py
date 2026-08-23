"""Build the distributable SQLite seed from validated extracted JSON."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import Base
from app.models import SourceDocument
from app.official_website import source_filename
from app.schemas import ExtractedQuestionBank
from app.services.import_service import ImportService


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("json", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    if args.output.exists():
        args.output.unlink()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{args.output}")
    Base.metadata.create_all(engine)
    settings = Settings(upload_dir=Path("/tmp/realieprep-seed-import"))
    bank = ExtractedQuestionBank.model_validate_json(
        args.json.read_text(encoding="utf-8"), strict=True
    )
    with Session(engine) as db:
        service = ImportService(db, settings)
        pending = service.save_pending(
            source_filename(args.source_url),
            args.sha256,
            bank,
            source_url=args.source_url,
        )
        source = service.confirm(pending.token)
        source.imported_at = datetime.now(UTC)
        db.commit()
        source = db.scalar(select(SourceDocument))
        assert source is not None and source.question_count == 300
    print(f"Built {args.output} with 300 validated questions")


if __name__ == "__main__":
    main()
