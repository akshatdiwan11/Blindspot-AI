from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class EvaluationRunRequest(BaseModel):
    dataset_id: int
    config: dict[str, Any] = Field(default_factory=dict, description="EvaluationConfig; task_type defaults to the project's evaluation task.")


class MetricOut(ORMModel):
    name: str
    value: float | None
    scope: str
    scope_key: str
    extra: dict[str, Any]


class RunSummary(ORMModel):
    id: int
    project_id: int
    dataset_id: int
    dataset_version: int
    task_type: str
    label: str
    status: str
    analysis_status: str
    total_records: int
    evaluated_records: int
    failure_count: int
    error_rate: float | None
    headline_metric: str | None
    headline_value: float | None
    duration_ms: int | None
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None = None


class RunDetail(RunSummary):
    config: dict[str, Any]
    metrics: list[MetricOut]
    discovery_summary: dict[str, Any]
    clustering_summary: dict[str, Any]
    dataset_name: str = ""
    failure_group_count: int = 0
    cluster_count: int = 0


class FailureGroupOut(ORMModel):
    id: int
    run_id: int
    rank: int
    name: str
    method: str
    conditions: list[dict[str, Any]]
    rule_text: str
    sample_size: int
    failures: int
    error_rate: float
    baseline_error_rate: float
    complement_error_rate: float | None
    difference: float
    lift: float | None
    ci_low: float
    ci_high: float
    p_value: float
    q_value: float
    reliability: str
    severity: str
    severity_score: float
    notes: list[str]


class CaseRecord(BaseModel):
    index: int
    case_id: str
    correct: bool
    score: float
    error_type: str
    input: str | None
    expected: str | None
    actual: str | None
    metadata: dict[str, Any]
    details: dict[str, Any]
    representative: bool = False


class FailureGroupDetail(FailureGroupOut):
    examples: list[CaseRecord]
    successes: list[CaseRecord]


class ClusterOut(ORMModel):
    id: int
    run_id: int
    cluster_index: int
    label: str
    method: str
    top_terms: list[str]
    size: int
    share_of_failures: float
    cohesion: float | None
    dominant_metadata: list[dict[str, Any]]
    representative_indices: list[int]


class ClusterDetail(ClusterOut):
    examples: list[CaseRecord]


class RunComparison(BaseModel):
    run_a: RunSummary
    run_b: RunSummary
    metrics: list[dict[str, Any]]
    error_rate_test: dict[str, Any] | None
    groups: list[dict[str, Any]]
    verdict: str
    comparable: bool
    notes: list[str]
