# Database model

```mermaid
erDiagram
    SOURCE_DOCUMENT ||--o{ QUESTION : contains
    CATEGORY ||--o{ QUESTION : groups
    QUESTION ||--|{ QUESTION_OPTION : has
    QUIZ_SESSION ||--o{ QUIZ_BATCH : contains
    QUIZ_BATCH ||--|{ QUESTION_VIEW : displays
    QUESTION ||--o{ QUESTION_VIEW : viewed
    QUESTION_VIEW ||--o| ANSWER_ATTEMPT : answered_as
    QUESTION ||--o{ ANSWER_ATTEMPT : receives
    QUIZ_SESSION ||--o{ ANSWER_ATTEMPT : contains

    SOURCE_DOCUMENT {
        int id PK
        string filename
        string source_url
        string sha256 UK
        datetime imported_at
        int question_count
        int category_count
        string validation_status
    }
    CATEGORY {
        int id PK
        int number UK
        string name
    }
    QUESTION {
        int id PK
        int source_document_id FK
        int category_id FK
        int source_question_number
        string official_id UK
        date source_updated_on
        string stable_key UK
        text text
        string correct_option
        string image_path
        int source_page
    }
    QUESTION_OPTION {
        int id PK
        int question_id FK
        string label
        text text
        string image_path
    }
    QUIZ_SESSION {
        int id PK
        date session_date UK
        datetime started_at
        datetime completed_at
    }
    QUIZ_BATCH {
        int id PK
        int quiz_session_id FK
        int batch_number
        bool allow_repeats
        string selection_mode
        datetime submitted_at
    }
    QUESTION_VIEW {
        int id PK
        int question_id FK
        int quiz_batch_id FK
        datetime shown_at
        bool was_repeat
    }
    ANSWER_ATTEMPT {
        int id PK
        int question_id FK
        int quiz_session_id FK
        int question_view_id FK
        string selected_option
        bool correct
        string mistake_type
        datetime answered_at
    }
```

`question_views` is the authoritative exposure ledger. Attempts are immutable historical events;
later retries create new views and attempts instead of overwriting earlier performance.
`quiz_sessions.session_date` is derived from `APP_TIMEZONE` (Europe/Prague by default), independent
of the host operating system's timezone.
