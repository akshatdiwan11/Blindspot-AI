import numpy as np
import pytest

from app.evaluation.config import DiscoveryConfig
from app.failure_discovery.engine import discover_failures
from app.failure_discovery.features import apply_conditions, build_feature_frame, count_dates, detect_script, rule_text
from app.failure_discovery.stats import benjamini_hochberg, two_proportion_test, wilson_interval


def test_wilson_interval_properties():
    lo, hi = wilson_interval(48, 120)
    assert lo < 0.4 < hi
    assert wilson_interval(0, 0) == (0.0, 1.0)
    small = wilson_interval(2, 5)
    big = wilson_interval(200, 500)
    assert (small[1] - small[0]) > (big[1] - big[0])


def test_benjamini_hochberg_monotone_and_bounded():
    q = benjamini_hochberg([0.01, 0.04, 0.03, 0.5])
    assert q == pytest.approx([0.04, 0.16 / 3, 0.16 / 3, 0.5])
    assert benjamini_hochberg([]) == []


def test_two_proportion_test():
    t = two_proportion_test(50, 100, 20, 100)
    assert t["p_value"] < 0.001 and t["difference"] == pytest.approx(-0.3)


def test_text_feature_helpers():
    assert count_dates("Issued on 3 March 2025. Deadline: 15 December 2025, exam 2025-12-20") == 3
    assert count_dates("अंतिम तिथि 15 दिसंबर 2025 है") == 1
    assert detect_script("अंतिम तिथि") == "devanagari"
    assert detect_script("deadline") == "latin"


def _synthetic(n=600, seed=0):
    rng = np.random.default_rng(seed)
    records, fails = [], []
    for i in range(n):
        lang = rng.choice(["English", "Hindi"], p=[0.8, 0.2])
        doc = rng.choice(["Invoice", "Notice", "Form"])
        noise = rng.choice(["a", "b", "c", "d"])
        p = 0.45 if lang == "Hindi" else 0.04
        records.append({"lang": lang, "doc": doc, "noise": noise, "e": "x", "a": "y", "id": str(i)})
        fails.append(rng.random() < p)
    return records, np.array(fails)


def test_discovers_planted_group_and_ignores_noise():
    records, y = _synthetic()
    mapping = {"expected_column": "e", "actual_column": "a", "metadata_columns": ["lang", "doc", "noise", "id"]}
    ff = build_feature_frame(records, list(range(len(records))), mapping)
    assert any(e["feature"] == "id" for e in ff.excluded)  # identifier-like column dropped
    res = discover_failures(ff, y, DiscoveryConfig())
    reliable = [g for g in res.groups if g.reliability == "reliable"]
    assert reliable and reliable[0].conditions == [{"feature": "lang", "op": "==", "value": "Hindi"}]
    assert all("noise" not in g.name for g in reliable)
    top = reliable[0]
    assert top.ci[0] > res.baseline_error_rate
    assert top.q_value <= 0.05


def test_no_groups_on_pure_noise():
    rng = np.random.default_rng(3)
    records = [{"m": rng.choice(list("abcdef")), "e": "x", "a": "y"} for _ in range(400)]
    y = rng.random(400) < 0.1
    ff = build_feature_frame(records, list(range(400)), {"expected_column": "e", "actual_column": "a", "metadata_columns": ["m"]})
    res = discover_failures(ff, y, DiscoveryConfig())
    assert not [g for g in res.groups if g.reliability == "reliable"]


def test_tiny_groups_never_reliable():
    records = [{"m": "rare" if i < 6 else "common", "e": "x", "a": "y"} for i in range(200)]
    y = np.array([i < 6 or i % 20 == 0 for i in range(200)])
    ff = build_feature_frame(records, list(range(200)), {"expected_column": "e", "actual_column": "a", "metadata_columns": ["m"]})
    res = discover_failures(ff, y, DiscoveryConfig(min_group_size=20))
    assert not any("rare" in g.name for g in res.groups)


def test_leaky_feature_is_dropped():
    rng = np.random.default_rng(1)
    y = rng.random(300) < 0.2
    records = [{"was_wrong": "yes" if f else "no", "g": rng.choice(["a", "b"]), "e": "x", "a": "y"} for f in y]
    ff = build_feature_frame(records, list(range(300)), {"expected_column": "e", "actual_column": "a", "metadata_columns": ["was_wrong", "g"]})
    res = discover_failures(ff, y, DiscoveryConfig())
    assert any("leakage" in e["reason"] for e in res.summary["features_excluded"])
    assert all("was_wrong" not in g.name for g in res.groups)


def test_missing_values_are_a_level_and_rules_reapply():
    records = [{"src": None if i % 4 == 0 else "pdf", "n": str(i % 50), "e": "x", "a": "y"} for i in range(200)]
    ff = build_feature_frame(records, list(range(200)), {"expected_column": "e", "actual_column": "a", "metadata_columns": ["src", "n"]})
    assert (ff.frame["src"] == "(missing)").sum() == 50
    mask = apply_conditions(ff.frame, [{"feature": "n", "op": "between", "low": 10, "high": 20}])
    assert mask.sum() == 40
    assert rule_text([{"feature": "a", "op": "==", "value": "x"}, {"feature": "n", "op": "between", "low": 2, "high": None}]) == "a = x\nAND\nn ≥ 2"


def test_all_or_no_failures_handled():
    records = [{"m": "a", "e": "x", "a": "y"} for _ in range(50)]
    ff = build_feature_frame(records, list(range(50)), {"expected_column": "e", "actual_column": "a", "metadata_columns": []})
    assert discover_failures(ff, np.zeros(50, bool), DiscoveryConfig()).groups == []
    assert discover_failures(ff, np.ones(50, bool), DiscoveryConfig()).groups == []


def _interaction(n=6000, seed=11):
    """Failures come only from chat messages from IN; other IN rows fail at the normal rate."""
    rng = np.random.default_rng(seed)
    records, fails = [], []
    for _ in range(n):
        ch, rg = rng.choice(["email", "chat", "phone"]), rng.choice(["EU", "US", "IN", "BR"])
        p = 0.45 if (ch == "chat" and rg == "IN") else 0.08
        records.append({"channel": ch, "region": rg, "e": "x", "a": "y"})
        fails.append(rng.random() < p)
    return records, np.array(fails)


def test_reports_the_narrow_rule_that_explains_a_broad_one():
    records, y = _interaction()
    ff = build_feature_frame(records, list(range(len(records))), {"expected_column": "e", "actual_column": "a", "metadata_columns": ["channel", "region"]})
    res = discover_failures(ff, y, DiscoveryConfig())
    reliable = [g for g in res.groups if g.reliability == "reliable"]
    assert reliable, "the planted interaction must be found"
    top = reliable[0]
    assert {(c["feature"], c.get("value")) for c in top.conditions} == {("channel", "chat"), ("region", "IN")}
    assert any("broader rule" in note for note in top.notes)
    # The broad parents are not reported as separate weaknesses.
    assert not any(g.conditions == [{"feature": "region", "op": "==", "value": "IN"}] for g in reliable)
