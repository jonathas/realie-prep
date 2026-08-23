from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "RealiePrep"
    database_url: str = "sqlite:///./data/realieprep.db"
    expected_question_count: int = 300
    expected_category_count: int = 30
    expected_questions_per_category: int = 10
    passing_grade_percent: float = 60
    weak_topic_min_attempts: int = 5
    admin_password: str = ""
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://localhost:8000",
    ]
    upload_dir: Path = Path("./data/uploads")
    official_bank_url: str = "https://cestina-pro-cizince.cz/obcanstvi/databanka-uloh/"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
