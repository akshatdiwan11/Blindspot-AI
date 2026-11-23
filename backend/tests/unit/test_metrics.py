import math

import pytest

from app.evaluation.config import EvaluationConfig
from app.evaluation.json_eval import flatten, schema_errors
from app.evaluation.runner import evaluate_records
from app.utils.text import normalize_text, token_prf

M = {"expected_column": "e", "actual_column": "a"}


def metric(out, name, scope="overall", key=""):
    return next(m.value for m in out.metrics if m.name == name and m.scope == scope and m.scope_key == key)


def test_normalization_and_token_f1():
    assert normalize_text("The  Policy, was UPDATED!") == "policy was updated"
    assert normalize_text("अंतिम तिथि।") == "अंतिम तिथि"
    p, r, f = token_prf("policy is unchanged", "policy was updated")
    assert (p, r) == (1 / 3, 1 / 3) and math.isclose(f, 1 / 3)
    assert token_prf("", "") == (1.0, 1.0, 1.0)


def test_text_metrics():
    recs = [{"e": "15 December", "a": "20 December"}, {"e": "Akshat Diwan", "a": "akshat diwan."}, {"e": "x", "a": None}]
    out, excluded = evaluate_records(recs, M, EvaluationConfig(task_type="text"))
    assert excluded == []
    assert metric(out, "exact_match") == 0
    assert metric(out, "normalized_exact_match") == pytest.approx(1 / 3)
    assert metric(out, "token_f1") == pytest.approx((0.5 + 1 + 0) / 3)
    assert [c.error_type for c in out.cases] == ["partial_match", "", "empty_output"]


def test_text_token_f1_threshold():
    recs = [{"e": "the policy was updated today", "a": "policy was updated"}]
    cfg = EvaluationConfig(task_type="text", text={"match": "token_f1", "threshold": 0.7})
    out, _ = evaluate_records(recs, M, cfg)
    assert out.cases[0].correct  # F1 = 0.857


def test_missing_expected_is_excluded():
    out, excluded = evaluate_records([{"e": None, "a": "x"}, {"e": "y", "a": "y"}], M, EvaluationConfig(task_type="text"))
    assert excluded == [0] and len(out.cases) == 1


def test_classification_metrics_match_hand_computation():
    y = [("spam", "spam"), ("spam", "ham"), ("ham", "ham"), ("ham", "ham"), ("fraud", "ham"), ("fraud", "fraud")]
    recs = [{"e": e, "a": a} for e, a in y]
    out, _ = evaluate_records(recs, M, EvaluationConfig(task_type="classification", classification={"positive_label": "fraud"}))
    assert metric(out, "accuracy") == pytest.approx(4 / 6)
    # ham: P = 2/4, R = 1 ; spam: P = 1, R = 0.5 ; fraud: P = 1, R = 0.5
    assert metric(out, "precision", "class", "ham") == pytest.approx(0.5)
    assert metric(out, "recall", "class", "spam") == pytest.approx(0.5)
    assert metric(out, "precision_macro") == pytest.approx((0.5 + 1 + 1) / 3)
    assert metric(out, "binary_recall") == pytest.approx(0.5)
    assert metric(out, "false_positives", "class", "ham") == 2
    assert metric(out, "false_negatives", "class", "fraud") == 1
    cm = out.extras["confusion_matrix"]
    assert sum(map(sum, cm)) == 6


def test_classification_case_insensitive_by_default():
    out, _ = evaluate_records([{"e": "Fraud", "a": " fraud "}], M, EvaluationConfig(task_type="classification"))
    assert out.cases[0].correct


def test_json_field_level_metrics():
    recs = [
        {"e": '{"name": "A", "date": "2025-01-01", "amount": 10}', "a": '{"name": "a", "date": "2025-01-02", "amount": 10.0, "x": 1}'},
        {"e": '{"name": "B"}', "a": "```json\n{\"name\": \"B\"}\n```"},
        {"e": '{"name": "C"}', "a": "{broken"},
        {"e": "not json", "a": "{}"},
    ]
    out, excluded = evaluate_records(recs, M, EvaluationConfig(task_type="json"))
    assert excluded == [3]
    assert metric(out, "exact_json_match") == pytest.approx(1 / 3)
    assert metric(out, "invalid_json_rate") == pytest.approx(1 / 3)
    assert metric(out, "field_accuracy") == pytest.approx(3 / 5)  # name, amount, name correct of 5 expected fields
    assert metric(out, "extra_fields") == 1
    assert metric(out, "field_accuracy", "field", "date") == 0
    assert [c.error_type for c in out.cases] == ["wrong_values", "", "invalid_json"]


def test_json_schema_validation():
    schema = {"type": "object", "required": ["name", "amount"], "properties": {"amount": {"type": "number"}}}
    assert schema_errors({"name": "x", "amount": "ten"}, schema) == ["$.amount: expected number"]
    assert schema_errors({"name": "x"}, schema) == ["$.amount: required field missing"]
    assert flatten({"a": {"b": 1}, "c": [1]}) == {"a.b": 1, "c": [1]}
