# Architecture

RealiePrep has two deliberately separated workflows.

```mermaid
flowchart LR
    WEB[Official question website] --> SC[Deterministic HTML scraper]
    SC --> PV[Pydantic validation]
    PV --> BV[Business validation]
    BV --> PR[Admin preview]
    PR -->|confirm| TX[Transactional synchronization]
    TX --> DB[(Database)]

    DB --> QS[Question selection]
    QS --> API[FastAPI]
    API --> UI[React TypeScript UI]
    UI --> GR[Deterministic grading]
    GR --> DB
    DB --> ST[Statistics service]
    ST --> UI
```

The React application is built by Vite and served by Nginx. Nginx proxies `/api` to FastAPI.
FastAPI route handlers delegate synchronization, quiz, and statistics behavior to services.
SQLAlchemy models provide database-neutral persistence. SQLite is the default.

The shipped seed is copied into the persistent data volume only when no runtime database exists.
Normal startup never overwrites progress.
