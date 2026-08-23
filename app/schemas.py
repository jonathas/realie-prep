from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

OptionLabel = Literal["A", "B", "C", "D"]


class ExtractedOption(BaseModel):
    model_config = ConfigDict(strict=True)
    label: OptionLabel
    text: str = Field(min_length=1)
    image_path: str | None = None


class ExtractedQuestion(BaseModel):
    model_config = ConfigDict(strict=True)
    category: str = Field(min_length=1)
    category_number: int | None = None
    question_number: int = Field(gt=0)
    official_id: str | None = None
    source_updated_on: date | None = None
    text: str = Field(min_length=1)
    options: list[ExtractedOption]
    correct_answer: OptionLabel
    source_page: int | None = Field(default=None, gt=0)
    image_path: str | None = None

    @model_validator(mode="after")
    def validate_options(self) -> "ExtractedQuestion":
        labels = [option.label for option in self.options]
        if len(labels) != 4 or set(labels) != {"A", "B", "C", "D"}:
            raise ValueError("options must contain exactly one each of A, B, C and D")
        return self

    @property
    def stable_key(self) -> str:
        prefix = str(self.category_number) if self.category_number is not None else self.category
        return f"{prefix}.{self.question_number}"


class ExtractedQuestionBank(BaseModel):
    model_config = ConfigDict(strict=True)
    questions: list[ExtractedQuestion]


class OptionOut(BaseModel):
    label: str
    text: str
    image_path: str | None = None


class QuestionOut(BaseModel):
    id: int
    stable_key: str
    category: str
    text: str
    image_path: str | None = None
    options: list[OptionOut]


class BatchOut(BaseModel):
    id: int
    batch_number: int
    submitted: bool
    allow_repeats: bool
    selection_mode: str
    questions: list[QuestionOut]


class SessionOut(BaseModel):
    id: int
    date: str
    batches: list[BatchOut]
    bank_empty: bool = False


class AnswerIn(BaseModel):
    question_view_id: int
    selected_option: OptionLabel


class SubmitBatchIn(BaseModel):
    answers: list[AnswerIn]


class AnswerResult(BaseModel):
    question_view_id: int
    question_id: int
    selected_option: str
    correct_option: str
    correct: bool


class BatchResult(BaseModel):
    score: int
    total: int
    accuracy: float
    results: list[AnswerResult]


class MistakeUpdate(BaseModel):
    mistake_type: Literal["vocabulary", "knowledge", "careless", "unknown"]


class SelectionMode(StrEnum):
    UNSEEN = "unseen"
    MIXED = "mixed"
    WEAK_TOPICS = "weak_topics"
    INCORRECT = "incorrect"
    MISSED_TWICE = "missed_twice"


class NewBatchIn(BaseModel):
    allow_repeats: bool = False
    mode: SelectionMode = SelectionMode.UNSEEN


class ImportPreviewOut(BaseModel):
    token: str
    filename: str
    sha256: str
    question_count: int
    category_count: int
    option_count: int
    valid: bool
    errors: list[str]


class AdminStatusOut(BaseModel):
    database_status: str
    filename: str | None = None
    source_url: str | None = None
    sha256: str | None = None
    imported_at: datetime | None = None
    validation_status: str | None = None
    question_count: int = 0
    category_count: int = 0
    option_count: int = 0
