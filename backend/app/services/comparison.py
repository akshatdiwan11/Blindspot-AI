"""Compare evaluation runs, and measure a failure-group rule on any run."""
from __future__ import annotations

from typing import Any

import numpy as np

from app.failure_discovery.features import apply_conditions, build_feature_frame
from app.failure_discovery.stats import two_proportion_test, wilson_interval
from app.models import EvaluationRun

LOWER_IS_BETTER = {"failure_rate", "invalid_json_rate", "missing_fields", "extra_fields", "incorrect_field_values", "schema_violation_rate"}


def segment_stats(run: EvaluationRun, conditions: list[dict[str, Any]]) -> dict[str, Any]:
    """Error rate of `run` restricted to rows matching `conditions` (re-applied on this run's data)."""
    ds = run.dataset
    cases = run.case_results
    positions = [c["index"] for c in cases]
    extra = None
    if run.task_type == "classification":
        extra = {"expected_label": [c.get("details", {}).get("expected_label", "") for c in cases]}
    ff = build_feature_frame(ds.records, positions, ds.column_mapping or {}, derive=True, extra_categorical=extra)
    mask = apply_conditions(ff.frame, conditions)
    fails = np.array([not c["correct"] for c in cases])
    n, k = int(mask.sum()), int(fails[mask].sum())
    lo, hi = wilson_interval(k, n)
    return {"run_id": run.id, "rows": n, "failures": k, "error_rate": (k / n) if n else None, "ci_low": lo, "ci_high": hi,
            "accuracy": (1 - k / n) if n else None}


def compare_runs(a: EvaluationRun, b: EvaluationRun) -> dict[str, Any]:
    notes: list[str] = []
    comparable = a.task_type == b.task_type
    if not comparable:
        notes.append("The runs use different task types, so their metrics measure different things.")
    if a.dataset_id != b.dataset_id:
        notes.append("The runs use different datasets. Differences may come from the data as well as the model.")
    elif a.dataset_version != b.dataset_version:
        notes.append("The runs use different versions of the dataset.")
    if a.config != b.config:
        notes.append("The evaluation configurations differ (for example matching rules or thresholds).")

    ma = {(m.name, m.scope, m.scope_key): m.value for m in a.metrics}
    mb = {(m.name, m.scope, m.scope_key): m.value for m in b.metrics}
    metrics = []
    for key in sorted(set(ma) | set(mb), key=lambda k: (k[1] != "overall", k[1], k[2], k[0])):
        va, vb = ma.get(key), mb.get(key)
        delta = (vb - va) if (va is not None and vb is not None) else None
        lower_better = key[0] in LOWER_IS_BETTER
        direction = None
        if delta is not None and abs(delta) > 1e-9:
            direction = "improved" if (delta < 0) == lower_better else "declined"
        elif delta is not None:
            direction = "unchanged"
        metrics.append({"name": key[0], "scope": key[1], "scope_key": key[2], "run_a": va, "run_b": vb, "delta": delta,
                        "lower_is_better": lower_better, "direction": direction})

    test = None
    if a.evaluated_records and b.evaluated_records:
        test = two_proportion_test(a.failure_count, a.evaluated_records, b.failure_count, b.evaluated_records)
        test["significant"] = test["p_value"] < 0.05
    groups = []
    for g in a.failure_groups[:15]:
        seg_b = segment_stats(b, g.conditions)
        groups.append({"group_id": g.id, "name": g.name, "run_a_error_rate": g.error_rate, "run_a_rows": g.sample_size,
                       "run_b_error_rate": seg_b["error_rate"], "run_b_rows": seg_b["rows"],
                       "delta": (seg_b["error_rate"] - g.error_rate) if seg_b["error_rate"] is not None else None})
    if test is None:
        verdict = "Not enough data to compare."
    elif not test["significant"]:
        verdict = f"No statistically significant change in failure rate ({a.error_rate:.1%} → {b.error_rate:.1%}, p = {test['p_value']:.2f})."
    elif b.error_rate < a.error_rate:
        verdict = f"Failure rate improved from {a.error_rate:.1%} to {b.error_rate:.1%} (p = {test['p_value']:.3f})."
    else:
        verdict = f"Failure rate got worse, from {a.error_rate:.1%} to {b.error_rate:.1%} (p = {test['p_value']:.3f})."
    return {"metrics": metrics, "error_rate_test": test, "groups": groups, "verdict": verdict, "comparable": comparable, "notes": notes}
