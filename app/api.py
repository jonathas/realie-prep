from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.models import MistakeType, QuestionOption, SourceDocument
from app.official_website import OfficialWebsiteScraper, ScrapingError, source_filename
from app.schemas import (
    AdminStatusOut,
    BatchOut,
    BatchResult,
    ImportPreviewOut,
    MistakeUpdate,
    NewBatchIn,
    SessionOut,
    SubmitBatchIn,
)
from app.services.import_service import ImportService, ImportValidationError
from app.services.quiz_service import QuizError, QuizService
from app.services.statistics_service import StatisticsService

router = APIRouter(prefix="/api")


def require_admin(
    x_admin_password: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    if settings.admin_password and x_admin_password != settings.admin_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin password"
        )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/quiz/today", response_model=SessionOut)
def today(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> SessionOut:
    return QuizService(db, settings).get_or_create_current()


@router.post("/quiz/batches", response_model=BatchOut, status_code=status.HTTP_201_CREATED)
def new_batch(
    request: NewBatchIn,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> BatchOut:
    try:
        return QuizService(db, settings).new_batch(request)
    except QuizError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/quiz/batches/{batch_id}/submit", response_model=BatchResult)
def submit_batch(
    batch_id: int,
    submission: SubmitBatchIn,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> BatchResult:
    try:
        return QuizService(db, settings).submit(batch_id, submission)
    except QuizError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.patch("/quiz/views/{view_id}/mistake", status_code=status.HTTP_204_NO_CONTENT)
def classify_mistake(
    view_id: int,
    update: MistakeUpdate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> None:
    try:
        QuizService(db, settings).classify(view_id, MistakeType(update.mistake_type))
    except QuizError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/stats")
def stats(
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> dict[str, object]:
    return StatisticsService(db, settings).calculate()


@router.get("/admin/status", response_model=AdminStatusOut, dependencies=[Depends(require_admin)])
def admin_status(db: Session = Depends(get_db)) -> AdminStatusOut:
    source = db.scalar(select(SourceDocument).order_by(SourceDocument.imported_at.desc()))
    if source is None:
        return AdminStatusOut(database_status="ready")
    return AdminStatusOut(
        database_status="ready",
        filename=source.filename,
        source_url=source.source_url,
        sha256=source.sha256,
        imported_at=source.imported_at,
        validation_status=source.validation_status.value,
        question_count=source.question_count,
        category_count=source.category_count,
        option_count=db.scalar(select(func.count(QuestionOption.id))) or 0,
    )


@router.post(
    "/admin/sync/preview",
    response_model=ImportPreviewOut,
    dependencies=[Depends(require_admin)],
)
async def preview_sync(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ImportPreviewOut:
    service = ImportService(db, settings)
    try:
        scraped = await OfficialWebsiteScraper(settings.official_bank_url).scrape()
        service.ensure_new_hash(scraped.sha256)
        pending = service.save_pending(
            source_filename(scraped.source_url),
            scraped.sha256,
            scraped.bank,
            source_url=scraped.source_url,
            assets=scraped.assets,
        )
        return service.preview(pending)
    except ImportValidationError as exc:
        raise HTTPException(status_code=409, detail=exc.errors) from exc
    except ScrapingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/admin/sync/{token}/confirm",
    response_model=AdminStatusOut,
    dependencies=[Depends(require_admin)],
)
def confirm_sync(
    token: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AdminStatusOut:
    service = ImportService(db, settings)
    try:
        service.confirm(token)
    except ImportValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors) from exc
    return admin_status(db)
