"""Helpers to turn stored records + case results into API-facing case objects."""
from __future__ import annotations

from typing import Any

from app.models import Dataset, EvaluationRun


def case_lookup(run: EvaluationRun) -> dict[int, dict[str, Any]]:
    return {c["index"]: c for c in run.case_results}


def build_case(dataset: Dataset, run: EvaluationRun, index: int, lookup: dict[int, dict[str, Any]] | None = None, representative: bool = False) -> dict[str, Any] | None:
    lookup = lookup if lookup is not None else case_lookup(run)
    c = lookup.get(index)
    if c is None or index >= len(dataset.records):
        return None
    rec = dataset.records[index]
    mapping = dataset.column_mapping or {}
    meta_cols = mapping.get("metadata_columns", [])
    return {
        "index": index,
        "case_id": c["case_id"],
        "correct": c["correct"],
        "score": c["score"],
        "error_type": c["error_type"],
        "input": rec.get(mapping.get("input_column")) if mapping.get("input_column") else None,
        "expected": rec.get(mapping.get("expected_column")),
        "actual": rec.get(mapping.get("actual_column")),
        "metadata": {m: rec.get(m) for m in meta_cols},
        "details": c.get("details", {}),
        "representative": representative,
    }
