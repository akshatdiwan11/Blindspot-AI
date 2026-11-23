"""Experiment lab: track proposed experiments and record *measured* results.

An experiment never reports an improvement unless at least one measured result exists.
Results come from either a manual entry or from re-applying the target failure group's rule
to a new evaluation run (measured by the engine).
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ValidationFailed
from app.failure_discovery.stats import two_proportion_test
from app.models import EvaluationRun, Experiment, ExperimentResult, FailureGroup
from app.services.activity import log_activity
from app.services.comparison import segment_stats

STATUSES = ("recommended", "planned", "running", "completed", "abandoned")
TRANSITIONS = {
    "recommended": {"planned", "running", "abandoned"},
    "planned": {"running", "abandoned", "recommended"},
    "running": {"completed", "planned", "abandoned"},
    "completed": {"running"},
    "abandoned": {"planned"},
}


def change_status(db: Session, exp: Experiment, new: str) -> None:
    if new == exp.status:
        return
    if new not in TRANSITIONS.get(exp.status, set()):
        raise ConflictError(f"An experiment cannot move from '{exp.status}' to '{new}'.")
    if new == "completed" and not exp.results:
        raise ConflictError("Record at least one measured result before marking the experiment completed.")
    exp.status = new
    log_activity(db, "experiment", f"Experiment '{exp.title}' marked {new}.", exp.project_id, f"/experiments?focus={exp.id}")


def measure_from_runs(db: Session, exp: Experiment, candidate: EvaluationRun) -> ExperimentResult:
    if exp.baseline_run_id is None:
        raise ValidationFailed("This experiment has no baseline run to compare against.")
    baseline = db.get(EvaluationRun, exp.baseline_run_id)
    if baseline is None:
        raise ValidationFailed("The baseline run no longer exists.")
    if candidate.id == baseline.id:
        raise ValidationFailed("Choose a different run from the baseline.")
    if candidate.project_id != exp.project_id:
        raise ValidationFailed("The candidate run must belong to the same project.")
    group = db.get(FailureGroup, exp.failure_group_id) if exp.failure_group_id else None
    details: dict[str, Any] = {"baseline_run_id": baseline.id, "candidate_run_id": candidate.id}
    if group is not None:
        b, c = segment_stats(baseline, group.conditions), segment_stats(candidate, group.conditions)
        if not c["rows"]:
            raise ValidationFailed("No rows in the candidate run match the target failure group's rule.")
        test = two_proportion_test(b["failures"], b["rows"], c["failures"], c["rows"])
        name = f"Error rate in failure group: {group.name}"
        details.update({"segment_rule": group.rule_text, "baseline": b, "candidate": c, "test": test})
        base_val, new_val = b["error_rate"], c["error_rate"]
    else:
        test = two_proportion_test(baseline.failure_count, baseline.evaluated_records, candidate.failure_count, candidate.evaluated_records)
        name, base_val, new_val = "Overall error rate", baseline.error_rate, candidate.error_rate
        details["test"] = test
    details["overall"] = {"baseline_error_rate": baseline.error_rate, "candidate_error_rate": candidate.error_rate}
    res = ExperimentResult(metric_name=name, baseline_value=base_val, new_value=new_val, higher_is_better=False,
                           source="measured_from_runs", details=details)
    exp.results.append(res)
    exp.candidate_run_id = candidate.id
    log_activity(db, "experiment", f"Measured experiment '{exp.title}' on run #{candidate.id}.", exp.project_id, f"/experiments?focus={exp.id}")
    return res


def outcome(exp: Experiment) -> dict[str, Any]:
    """Summarise measured results. No results means no claim."""
    if not exp.results:
        return {"state": "not_measured", "message": "No measured results yet. Nothing can be concluded about this experiment."}
    r = exp.results[-1]
    if r.baseline_value is None:
        return {"state": "measured", "message": f"{r.metric_name}: {r.new_value:.4g} (no baseline recorded)."}
    delta = r.new_value - r.baseline_value
    better = (delta > 0) == r.higher_is_better and abs(delta) > 1e-12
    test = (r.details or {}).get("test")
    sig = test is not None and test.get("p_value", 1) < 0.05
    if abs(delta) <= 1e-12:
        state = "no_change"
    elif better:
        state = "improved" if (sig or test is None) else "improved_not_significant"
    else:
        state = "regressed" if (sig or test is None) else "regressed_not_significant"
    msg = {
        "improved": "Measured improvement", "improved_not_significant": "Improvement measured but not statistically significant",
        "regressed": "Measured regression", "regressed_not_significant": "Regression measured but not statistically significant",
        "no_change": "No measured change",
    }[state]
    if test is None:
        msg += " (manually entered result, no significance test)"
    return {"state": state, "message": f"{msg}: {r.metric_name} {r.baseline_value:.4g} → {r.new_value:.4g}.", "delta": delta,
            "p_value": test.get("p_value") if test else None}
