# AGENTS.md

## Architecture

- Keep FastAPI routes thin; put business behavior in services.
- Use SQLAlchemy ORM and retain practical PostgreSQL compatibility.
- Keep official-site scraping isolated in `app/official_website.py`.
- Use deterministic Python/SQL for selection, grading, and statistics.
- Keep the React frontend in strict TypeScript; do not add JavaScript source files.

## Validation and synchronization

- Validate external data with strict Pydantic models before database writes.
- Never partially replace a question bank; confirmation must remain transactional.
- Preserve official question and option wording from the website.
- Download and verify every official visual asset during synchronization.
- Keep source URL, content hash, retrieval date, official IDs, and attribution current.
- Never commit, bundle, or publish downloaded official questions, images, or populated databases.

## Database

- Every model change requires an Alembic migration.
- Do not identify questions solely by text; use stable topic/question keys.
- `question_views` is authoritative for exposure tracking.
- Keep batch selection and view creation in one transaction.

## Testing and quality

- New business behavior and bug fixes require tests.
- Run `pytest`, `ruff check .`, `mypy app`, frontend build, and frontend lint.
- Prefer small typed functions and focused modules.
- Update database and architecture docs when boundaries change.

## Git

- Use Conventional Commits and small logical commits.
- Preserve unrelated user changes and never use destructive reset commands.
