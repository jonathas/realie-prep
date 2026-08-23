from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import router
from app.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
dynamic_images = settings.upload_dir.parent / "question-images"
dynamic_images.mkdir(parents=True, exist_ok=True)
app.mount("/question-images", StaticFiles(directory=dynamic_images), name="question-images")
