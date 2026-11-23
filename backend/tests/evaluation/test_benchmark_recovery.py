"""Evaluation regression tests on the synthetic benchmarks.

These check that the discovery engine recovers the failure patterns that were planted in the
synthetic data, and that headline metrics stay stable (the generators are seeded).
"""
import pytest

from app.demo.catalog import DEMOS
from app.demo.scoring import score_recovery


def _load(client, key):
    r = client.post(f"/api/demo/{key}")
    assert r.status_code == 201, r.text
    info = r.json()
    run = client.get(f"/api/evaluations/{info['run_id']}").json()
    groups = client.get(f"/api/evaluations/{info['run_id']}/failure-groups", params={"limit": 100}).json()["items"]
    return run, groups


def _members(client, run_id, group):
    """Member case IDs of a group, recomputed from the stored rule on the run's data."""
    from app.database.session import SessionLocal
    from app.failure_discovery.features import apply_conditions, build_feature_frame
    from app.models import EvaluationRun
    with SessionLocal() as db:
        run = db.get(EvaluationRun, run_id)
        cases = run.case_results
        extra = {"expected_label": [c["details"].get("expected_label", "") for c in cases]} if run.task_type == "classification" else None
        ff = build_feature_frame(run.dataset.records, [c["index"] for c in cases], run.dataset.column_mapping, extra_categorical=extra)
        mask = apply_conditions(ff.frame, group["conditions"])
        return {c["case_id"] for c, m in zip(cases, mask) if m}


@pytest.mark.parametrize("key,patterns,min_recovered", [
    ("deadline_extraction", ["multi_date", "hindi", "unusual_format", "long_document"], 4),
    ("email_triage", ["hinglish", "very_short", "fraud_class"], 3),
    ("invoice_json", ["scanned", "multi_page"], 2),
])
def test_planted_patterns_are_recovered(client, key, patterns, min_recovered):
    run, groups = _load(client, key)
    _, truth = DEMOS[key].generate()
    scored = [{"name": g["name"], "reliability": g["reliability"], "member_case_ids": _members(client, run["id"], g)} for g in groups]
    result = score_recovery(scored, truth, patterns)
    assert result["recovered"] >= min_recovered, result


def test_no_false_alarm_on_random_metadata(client):
    """vendor_region / customer_tier were generated independently of errors: never a reliable group."""
    for key, col in (("invoice_json", "vendor_region"), ("email_triage", "customer_tier")):
        _, groups = _load(client, key)
        assert not [g for g in groups if g["reliability"] == "reliable" and all(c["feature"] == col for c in g["conditions"])]


def test_headline_metrics_are_stable(client):
    run, _ = _load(client, "deadline_extraction")
    assert run["evaluated_records"] == 900
    assert run["error_rate"] == pytest.approx(0.1744, abs=0.01)
    run, _ = _load(client, "email_triage")
    m = {x["name"]: x["value"] for x in run["metrics"] if x["scope"] == "overall"}
    assert m["accuracy"] == pytest.approx(1 - 0.1614, abs=0.01)
    per_class = {x["scope_key"]: x["value"] for x in run["metrics"] if x["scope"] == "class" and x["name"] == "recall"}
    assert per_class["Fraud"] < 0.75 < per_class["Technical"]


def test_clusters_found_on_demo(client):
    run, _ = _load(client, "deadline_extraction")
    clusters = client.get(f"/api/evaluations/{run['id']}/clusters").json()
    assert len(clusters) >= 2
    assert sum(c["size"] for c in clusters) == run["failure_count"]
    detail = client.get(f"/api/evaluations/{run['id']}/clusters/{clusters[0]['id']}").json()
    assert detail["examples"] and all(not e["correct"] for e in detail["examples"])
