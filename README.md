# RealiePrep

RealiePrep is a self-hosted study app for the Czech citizenship **Reálie** exam. The
repository and container images contain no official questions or images. On first use, an
administrator can explicitly download the bank from NPI ČR into the installation's private
local data volume.

The app serves a strict-TypeScript React interface through Nginx and a typed FastAPI API.
Question selection, grading, repetition, and statistics are deterministic Python/SQL—not AI.

## Features

- User-initiated download from the official 300-question, 30-topic bank
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

Open <http://localhost:8000>. On first start, the backend creates an empty migrated database at
`./data/realieprep.db`. Open **Admin**, acknowledge the official source, and choose
**Download official bank**. The app validates a preview before installing it locally.

By default Docker binds only to `127.0.0.1`, so it is not reachable from other machines.
Container recreation preserves the downloaded bank and study progress in `./data`.

## Configuration

| Variable | Default | Purpose |
|---|---:|---|
| `DATABASE_URL` | `sqlite:///./data/realieprep.db` | SQLAlchemy database URL |
| `BIND_ADDRESS` | `127.0.0.1` | Host interface exposed by Docker Compose |
| `APP_PORT` | `8000` | Host port exposed by Docker Compose |
| `DATA_DIR` | `./data` | Private host directory for the local bank and study progress |
| `EXPECTED_QUESTION_COUNT` | `300` | Required imported question count |
| `EXPECTED_CATEGORY_COUNT` | `30` | Required imported topic count |
| `EXPECTED_QUESTIONS_PER_CATEGORY` | `10` | Required questions per topic |
| `PASSING_GRADE_PERCENT` | `60` | Readiness threshold shown in stats |
| `WEAK_TOPIC_MIN_ATTEMPTS` | `5` | Minimum sample before weak-topic ranking |
| `ADMIN_PASSWORD` | empty | Optional locally stored password for admin API access |
| `UPLOAD_DIR` | `./data/uploads` | Temporary validated import previews |
| `OFFICIAL_BANK_URL` | official NPI database URL | Source checked by admin sync |

## Home server and LAN hosting

The default `127.0.0.1` binding is intentionally accessible only from the machine running
RealiePrep. To run it on a home server and use it from a laptop, phone, or another computer, edit
the server's `.env` file:

```env
BIND_ADDRESS=0.0.0.0
APP_PORT=8000
ADMIN_PASSWORD=replace-with-a-long-random-secret
```

You can generate an admin password on the server with:

```bash
openssl rand -hex 32
```

Apply the configuration:

```bash
docker compose up -d --build
```

Then open `http://<server-ip>:8000` from another device on the same network—for example,
`http://192.168.1.50:8000`. If mDNS is available, a hostname such as
`http://my-server.local:8000` may also work. On Linux, `hostname -I` usually shows the server's LAN
address.

Do not forward port 8000 from your router to the public internet. For remote access, prefer a
private VPN such as Tailscale. If you deliberately publish RealiePrep through a reverse proxy, use
HTTPS and keep a strong `ADMIN_PASSWORD`; the password is sent in an HTTP request header. Ensure
the host firewall permits port 8000 only from networks that should have access.

Back up `DATA_DIR`—by default `./data`—to preserve the downloaded question bank, answers, and
statistics. Updating or recreating containers does not remove this directory.

## Studying and repetition

Opening Study creates—or returns—the current unsubmitted batch. Refreshing does not consume
questions. By default, selection uses questions absent from `question_views`. Selection and
view creation happen in one transaction. Once unseen questions are exhausted, review priority
is: missed twice, weakest categories, previously incorrect, then least recently shown.

Overall accuracy uses every attempt. First-attempt accuracy uses only the earliest attempt for
each question and is the primary passing-grade comparison.

## Downloading and updating the official bank

New installations start empty and make no automatic request to NPI. Open **Admin**, review the
source notice, and explicitly select **Download official bank**. RealiePrep then reads the official
structured HTML directly, downloads its visual assets, and previews the result. Synchronization
requires exactly 300 questions, 30 topics, four A/B/C/D choices, unique stable IDs, and one valid
answer per question. Confirmation caches the bank in `./data`; ordinary startup and study sessions
never contact NPI.

Later, **Check official source** performs a user-requested update check. An identical canonical
bank is rejected as already current. Confirming changed content replaces the local bank and resets
study progress transactionally.

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

GitHub Actions runs these checks and a clean Docker build and startup test on every push and pull
request. The Docker check starts with an empty data directory and does not download the official
question bank.

## Database migrations

Create an Alembic migration after every model change:

```bash
.venv/bin/alembic revision --autogenerate -m "describe change"
.venv/bin/alembic upgrade head
```

## Scraper maintenance

```bash
.venv/bin/python scripts/scrape_official_site.py \
  --output /tmp/questions.json --assets /tmp/realieprep-question-images
```

This developer command writes only to caller-selected local paths. Never commit or publish its
output. Normal users should use the validated Admin workflow instead.

## Architecture and API

See [architecture](docs/architecture.md) and the [database model](docs/database.md). Interactive
OpenAPI documentation is available at `/docs` on the backend service.

## Source content and rights

The official site states that NPI ČR exclusively owns the question-bank copyright. RealiePrep does
not redistribute that content: each administrator chooses whether to download it directly from the
official source for local self-study. Downloaded questions and images stay under `./data`, are ignored
by Git, and are not covered by the MIT license. See [NOTICE.md](NOTICE.md).

## Contributing

Use focused changes and Conventional Commits. Add regression tests for business behavior,
keep routes thin, and run the complete verification suite before opening a pull request.

## License

Application code is MIT licensed. See [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md).
