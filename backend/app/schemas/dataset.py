from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ORMModel


class ColumnMapping(BaseModel):
    input_column: str | None = None
    expected_column: str
    actual_column: str
    case_id_column: str | None = None
    metadata_columns: list[str] = Field(default_factory=list, max_length=60)

    @model_validator(mode="after")
    def _distinct(self):
        core = [c for c in (self.input_column, self.expected_column, self.actual_column, self.case_id_column) if c]
        if len(core) != len(set(core)):
            raise ValueError("Input, expected, actual and case ID must be different columns")
        if self.expected_column == self.actual_column:
            raise ValueError("Expected and actual output must be different columns")
        self.metadata_columns = [m for m in dict.fromkeys(self.metadata_columns) if m not in core]
        return self


class DatasetOut(ORMModel):
    id: int
    project_id: int
    name: str
    version: int
    file_format: str
    original_filename: str
    size_bytes: int
    row_count: int
    status: str
    is_synthetic: bool
    columns: list[dict[str, Any]]
    column_mapping: dict[str, Any] | None
    created_at: datetime


class DatasetDetail(DatasetOut):
    profile: dict[str, Any]


class DatasetPreview(BaseModel):
    dataset: DatasetOut
    profile: dict[str, Any]
    sample_rows: list[dict[str, Any]]
    total: int
    limit: int
    offset: int
    mapping_check: dict[str, Any] | None = None
