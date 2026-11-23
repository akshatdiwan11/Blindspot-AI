from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel

ModelCategory = Literal["classification", "text_generation", "question_answering", "structured_extraction", "llm_application"]
TaskType = Literal["classification", "text", "json"]

DEFAULT_TASK: dict[str, str] = {
    "classification": "classification",
    "text_generation": "text",
    "question_answering": "text",
    "structured_extraction": "json",
    "llm_application": "text",
}


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field("", max_length=2000)
    model_category: ModelCategory
    evaluation_task: TaskType | None = None
    llm_investigation_enabled: bool = False

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Project name cannot be blank")
        return v


class ProjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = Field(None, max_length=2000)
    llm_investigation_enabled: bool | None = None


class ProjectOut(ORMModel):
    id: int
    name: str
    description: str
    model_category: str
    evaluation_task: str
    llm_investigation_enabled: bool
    is_demo: bool
    created_at: datetime
    updated_at: datetime
    dataset_count: int = 0
    run_count: int = 0
    latest_run_id: int | None = None
    latest_error_rate: float | None = None
    latest_headline_value: float | None = None
    failure_group_count: int = 0
