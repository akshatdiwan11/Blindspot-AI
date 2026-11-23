"""Dispatches records to the task-specific evaluator."""
from __future__ import annotations

from typing import Any

from app.core.errors import ValidationFailed
from app.evaluation.classification_eval import evaluate_classification
from app.evaluation.config import EvaluationConfig
from app.evaluation.json_eval import _load, evaluate_json
from app.evaluation.text_eval import evaluate_text
from app.evaluation.types import EvaluationOutcome


def case_id_for(record: dict[str, Any], index: int, mapping: dict[str, Any]) -> str:
    cid_col = mapping.get("case_id_column")
    if cid_col and record.get(cid_col) is not None:
        return str(record[cid_col])
    return f"row-{index + 1}"


def evaluate_records(records: list[dict[str, Any]], mapping: dict[str, Any], config: EvaluationConfig) -> tuple[EvaluationOutcome, list[int]]:
    """Returns the outcome and the indices of excluded records (no usable expected output)."""
    exp_col, act_col = mapping["expected_column"], mapping["actual_column"]
    indices, case_ids, expected, actual, excluded = [], [], [], [], []
    for i, r in enumerate(records):
        exp = r.get(exp_col)
        if exp is None or (config.task_type == "json" and not _load(exp)[1]):
            excluded.append(i)
            continue
        indices.append(i)
        case_ids.append(case_id_for(r, i, mapping))
        expected.append(exp)
        actual.append(r.get(act_col))
    if not indices:
        if config.task_type == "json":
            raise ValidationFailed("No records can be evaluated as JSON: none of the expected outputs is valid JSON. "
                                   "If the outputs are plain text, choose the text task instead.")
        raise ValidationFailed("No records can be evaluated: every record is missing a usable expected output.")
    if config.task_type == "classification":
        out = evaluate_classification(indices, case_ids, expected, actual, config.classification)
    elif config.task_type == "text":
        out = evaluate_text(indices, case_ids, expected, actual, config.text)
    elif config.task_type == "json":
        out = evaluate_json(indices, case_ids, expected, actual, config.json_eval)
    else:  # pragma: no cover - guarded by the schema
        raise ValidationFailed(f"Unknown task type {config.task_type}")
    return out, excluded
