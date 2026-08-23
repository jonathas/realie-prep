# RealiePrep

RealiePrep is a self-hosted study app for the Czech citizenship **Reálie** exam. It
ships with a validated database of the 300 questions retrieved from the official NPI ČR
online question bank, so a new installation is ready to study immediately.

The app serves a strict-TypeScript React interface through Nginx and a typed FastAPI API.
Question selection, grading, repetition, and statistics are deterministic Python/SQL—not AI.

## Features

- Bundled 300-question, 30-topic bank with visual questions
- Unseen-first batches of 10 with no accidental repetition
- Refresh-safe daily sessions and “Show 10 more”
- Intentional repetition and focused review modes
- Deterministic grading and retained attempt history
- User-classified vocabulary, knowledge, careless, and unknown mistakes
- Overall and first-attempt accuracy, coverage, passing comparison, and topic performance
- Missed-twice and weakest-topic review priorities
- Validated, transactional synchronization with the official online database
- Persistent SQLite storage, SQLAlchemy portability, Alembic migrations, and Docker Compose

## Quick start

```bash
cp .env.example .env
docker compose up -d --build
```

Open <http://localhost:8000>. On first start, the backend copies the bundled seed into
`./data/realieprep.db`. Later container recreation preserves your progress in that file.

## Configuration

| Variable | Default | Purpose |
|---|---:|---|
| `DATABASE_URL` | `sqlite:///./data/realieprep.db` | SQLAlchemy database URL |
| `EXPECTED_QUESTION_COUNT` | `300` | Required imported question count |
| `EXPECTED_CATEGORY_COUNT` | `30` | Required imported topic count |
| `EXPECTED_QUESTIONS_PER_CATEGORY` | `10` | Required questions per topic |
| `PASSING_GRADE_PERCENT` | `60` | Readiness threshold shown in stats |
| `WEAK_TOPIC_MIN_ATTEMPTS` | `5` | Minimum sample before weak-topic ranking |
| `ADMIN_PASSWORD` | empty | Optional password for admin API access |
| `UPLOAD_DIR` | `./data/uploads` | Temporary validated import previews |
| `OFFICIAL_BANK_URL` | official NPI database URL | Source checked by admin sync |

## Studying and repetition

Opening Study creates—or returns—the current unsubmitted batch. Refreshing does not consume
questions. By default, selection uses questions absent from `question_views`. Selection and
view creation happen in one transaction. Once unseen questions are exhausted, review priority
is: missed twice, weakest categories, previously incorrect, then least recently shown.

Overall accuracy uses every attempt. First-attempt accuracy uses only the earliest attempt for
each question and is the primary passing-grade comparison.

## Updating the official bank

Open **Admin** and select **Check official source**. RealiePrep deterministically reads the
structured HTML, downloads its visual assets, and previews the result. Synchronization requires
exactly 300 questions, 30 topics, four A/B/C/D choices, unique stable IDs, and one valid answer
per question. Confirmation replaces the bank and resets study progress transactionally.

No PDF, OCR, or AI is involved. If NPI changes the website markup, the sync fails safely and the
current bank stays active. Identical canonical bank hashes are recognized as already up to date.

## Development

Backend:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev]'
DATABASE_URL=sqlite:///./data/realieprep.db .venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Verification:

```bash
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/mypy app
cd frontend && npm run build && npm run lint
```

## Database migrations

Create an Alembic migration after every model change:

```bash
.venv/bin/alembic revision --autogenerate -m "describe change"
.venv/bin/alembic upgrade head
```

## Rebuilding the bundled bank

```bash
.venv/bin/python scripts/scrape_official_site.py \
  --output /tmp/questions.json --assets frontend/public/question-images
.venv/bin/python scripts/build_seed.py /tmp/questions.json data/realieprep_seed.db \
  --source-url https://cestina-pro-cizince.cz/obcanstvi/databanka-uloh/ \
  --sha256 THE_REPORTED_SHA256
```

Always validate the generated bank, visual asset mapping, source date, hash, and applicable
redistribution terms before publishing it.

## Architecture and API

See [architecture](docs/architecture.md) and the [database model](docs/database.md). Interactive
OpenAPI documentation is available at `/docs` on the backend service.

## Source content and rights

The seeded question bank was retrieved from the official online database on 23 August 2026.
Its canonical question-data SHA-256 at retrieval is recorded in the bundled database. The official site
states that NPI ČR exclusively owns the question-bank copyright. See [NOTICE.md](NOTICE.md).
The MIT license applies to application code, not third-party question text or images.

## Contributing

Use focused changes and Conventional Commits. Add regression tests for business behavior,
keep routes thin, and run the complete verification suite before opening a pull request.

## License

Application code is MIT licensed. See [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md).
