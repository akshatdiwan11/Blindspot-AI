from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel

Status = Literal["recommended", "planned", "running", "completed", "abandoned"]


class ExperimentCreate(BaseModel):
    project_id: int
    title: str = Field(..., min_length=1, max_length=300)
    failure_group_id: int | None = None
    baseline_run_id: int | None = None
    hypothesis: str = Field("", max_length=4000)
    proposed_change: str = Field("", max_length=4000)
    test_procedure: str = Field("", max_length=4000)
    success_criterion: str = Field("", max_length=2000)
    risks: list[str] = Field(default_factory=list, max_length=20)
    status: Literal["planned", "running"] = "planned"
    notes: str = Field("", max_length=10000)


class ExperimentUpdate(BaseModel):
    status: Status | None = None
    title: str | None = Field(None, min_length=1, max_length=300)
    hypothesis: str | None = Field(None, max_length=4000)
    proposed_change: str | None = Field(None, max_length=4000)
    test_procedure: str | None = Field(None, max_length=4000)
    success_criterion: str | None = Field(None, max_length=2000)
    notes: str | None = Field(None, max_length=10000)
    risks: list[str] | None = Field(None, max_length=20)


class ManualResult(BaseModel):
    metric_name: str = Field(..., min_length=1, max_length=120)
    baseline_value: float | None = None
    new_value: float
    higher_is_better: bool = True
    notes: str = Field("", max_length=2000)


class MeasureRequest(BaseModel):
    candidate_run_id: int


class ExperimentResultOut(ORMModel):
    id: int
    metric_name: str
    baseline_value: float | None
    new_value: float
    higher_is_better: bool
    source: str
    details: dict[str, Any]
    notes: str
    recorded_at: datetime


class ExperimentOut(ORMModel):
    id: int
    project_id: int
    investigation_id: int | None
    failure_group_id: int | None
    baseline_run_id: int | None
    candidate_run_id: int | None
    title: str
    target_failure_group: str
    hypothesis: str
    proposed_change: str
    test_procedure: str
    baseline_metric_name: str
    baseline_metric_value: float | None
    success_criterion: str
    risks: list[str]
    evidence_refs: list[str]
    status: str
    source: str
    notes: str
    created_at: datetime
    updated_at: datetime
    results: list[ExperimentResultOut]
    outcome: dict[str, Any] = {}
