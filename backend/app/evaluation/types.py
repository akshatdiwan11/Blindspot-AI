from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CaseResult:
    index: int            # position in the dataset's record list
    case_id: str
    correct: bool
    score: float          # task-specific per-case score in [0, 1]
    error_type: str       # "" when correct
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"index": self.index, "case_id": self.case_id, "correct": self.correct, "score": round(self.score, 4), "error_type": self.error_type, "details": self.details}


@dataclass
class Metric:
    name: str
    value: float | None
    scope: str = "overall"
    scope_key: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationOutcome:
    task_type: str
    cases: list[CaseResult]
    metrics: list[Metric]
    headline_metric: str
    headline_value: float | None
    extras: dict[str, Any] = field(default_factory=dict)  # e.g. confusion matrix

    @property
    def failure_count(self) -> int:
        return sum(1 for c in self.cases if not c.correct)

    @property
    def error_rate(self) -> float | None:
        return self.failure_count / len(self.cases) if self.cases else None
