"""Structured (JSON) output evaluation (deterministic)."""
from __future__ import annotations

import json
from typing import Any

from app.evaluation.config import JsonEvalConfig
from app.evaluation.types import CaseResult, EvaluationOutcome, Metric

_MISSING = object()


def _load(s: str | None) -> tuple[Any, bool]:
    if s is None or not str(s).strip():
        return None, False
    text = str(s).strip()
    if text.startswith("```"):  # tolerate fenced model output: ```json ... ```
        text = text.strip("`")
        text = text[4:] if text.lower().startswith("json") else text
    try:
        return json.loads(text), True
    except json.JSONDecodeError:
        return None, False


def flatten(obj: Any, prefix: str = "") -> dict[str, Any]:
    """Flatten nested objects to dotted paths. Lists are kept as leaf values."""
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, dict) and v:
                out.update(flatten(v, path))
            else:
                out[path] = v
        return out
    return {prefix or "$": obj}


def _norm_value(v: Any, cfg: JsonEvalConfig) -> Any:
    if isinstance(v, str):
        s = " ".join(v.split())
        return s if cfg.case_sensitive_values else s.lower()
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, list):
        items = [_norm_value(x, cfg) for x in v]
        if cfg.list_order_insensitive:
            return sorted(items, key=lambda x: json.dumps(x, sort_keys=True, default=str))
        return items
    if isinstance(v, dict):
        return {k: _norm_value(x, cfg) for k, x in sorted(v.items())}
    return v


_TYPES = {"string": str, "number": (int, float), "integer": int, "boolean": bool, "object": dict, "array": list, "null": type(None)}


def schema_errors(value: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    """A small, dependency-free subset of JSON Schema: type, required, properties, enum, items."""
    errs: list[str] = []
    t = schema.get("type")
    if t:
        types = t if isinstance(t, list) else [t]
        ok = any(isinstance(value, _TYPES.get(x, object)) and not (x in ("number", "integer") and isinstance(value, bool)) for x in types)
        if not ok:
            return [f"{path}: expected {'/'.join(types)}"]
    if "enum" in schema and value not in schema["enum"]:
        errs.append(f"{path}: value not in enum")
    if isinstance(value, dict):
        for req in schema.get("required", []):
            if req not in value:
                errs.append(f"{path}.{req}: required field missing")
        for k, sub in (schema.get("properties") or {}).items():
            if k in value and isinstance(sub, dict):
                errs.extend(schema_errors(value[k], sub, f"{path}.{k}"))
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        for i, item in enumerate(value[:100]):
            errs.extend(schema_errors(item, schema["items"], f"{path}[{i}]"))
    return errs


def evaluate_json(indices: list[int], case_ids: list[str], expected: list[str], actual: list[str | None], cfg: JsonEvalConfig) -> EvaluationOutcome:
    cases: list[CaseResult] = []
    field_totals: dict[str, dict[str, int]] = {}
    invalid_json = invalid_expected = schema_violations = exact = 0
    total_expected_fields = total_correct_fields = total_missing = total_extra = total_wrong = 0

    for k, idx in enumerate(indices):
        exp_obj, exp_ok = _load(expected[k])
        if not exp_ok:
            invalid_expected += 1
            cases.append(CaseResult(idx, case_ids[k], False, 0.0, "invalid_expected_json", {"note": "expected output is not valid JSON"}))
            continue
        act_obj, act_ok = _load(actual[k])
        exp_flat = {p: _norm_value(v, cfg) for p, v in flatten(exp_obj).items()}
        for p in exp_flat:
            field_totals.setdefault(p, {"total": 0, "correct": 0, "missing": 0, "wrong": 0})["total"] += 1
        total_expected_fields += len(exp_flat)
        if not act_ok:
            invalid_json += 1
            for p in exp_flat:
                field_totals[p]["missing"] += 1
            total_missing += len(exp_flat)
            cases.append(CaseResult(idx, case_ids[k], False, 0.0, "invalid_json", {"missing_fields": list(exp_flat)[:30]}))
            continue
        act_flat = {p: _norm_value(v, cfg) for p, v in flatten(act_obj).items()}
        missing = [p for p in exp_flat if p not in act_flat]
        extra = [p for p in act_flat if p not in exp_flat]
        wrong = [p for p in exp_flat if p in act_flat and act_flat[p] != exp_flat[p]]
        correct_fields = len(exp_flat) - len(missing) - len(wrong)
        for p in missing:
            field_totals[p]["missing"] += 1
        for p in wrong:
            field_totals[p]["wrong"] += 1
        for p in exp_flat:
            if p not in missing and p not in wrong:
                field_totals[p]["correct"] += 1
        total_correct_fields += correct_fields
        total_missing += len(missing); total_extra += len(extra); total_wrong += len(wrong)
        is_exact = _norm_value(exp_obj, cfg) == _norm_value(act_obj, cfg)
        exact += is_exact
        field_acc = correct_fields / len(exp_flat) if exp_flat else 1.0
        s_errs = schema_errors(act_obj, cfg.json_schema) if cfg.json_schema else []
        schema_violations += bool(s_errs)
        if cfg.criterion == "exact":
            ok = is_exact or (cfg.ignore_extra_fields and not missing and not wrong)
        else:
            ok = field_acc >= cfg.field_threshold and (cfg.ignore_extra_fields or not extra)
        if ok and s_errs:
            ok = False
        if ok:
            etype = ""
        elif s_errs and not (missing or wrong):
            etype = "schema_violation"
        elif wrong:
            etype = "wrong_values"
        elif missing:
            etype = "missing_fields"
        else:
            etype = "extra_fields"
        cases.append(CaseResult(idx, case_ids[k], ok, field_acc, etype, {
            "field_accuracy": round(field_acc, 4), "missing_fields": missing[:30], "extra_fields": extra[:30],
            "wrong_fields": wrong[:30], "schema_errors": s_errs[:10],
        }))

    n = len(cases)
    acc = sum(c.correct for c in cases) / n if n else None
    metrics = [
        Metric("accuracy", acc, extra={"definition": f"cases passing the '{cfg.criterion}' criterion"}),
        Metric("exact_json_match", exact / n if n else None),
        Metric("field_accuracy", total_correct_fields / total_expected_fields if total_expected_fields else None),
        Metric("invalid_json_rate", invalid_json / n if n else None),
        Metric("missing_fields", float(total_missing)),
        Metric("extra_fields", float(total_extra)),
        Metric("incorrect_field_values", float(total_wrong)),
        Metric("failure_rate", 1 - acc if acc is not None else None),
    ]
    if cfg.json_schema:
        metrics.append(Metric("schema_violation_rate", schema_violations / n if n else None))
    per_field = []
    for p, t in sorted(field_totals.items(), key=lambda kv: -kv[1]["total"]):
        fa = t["correct"] / t["total"] if t["total"] else None
        per_field.append({"field": p, "accuracy": fa, **t})
        metrics.append(Metric("field_accuracy", fa, scope="field", scope_key=p, extra=t))
    error_types: dict[str, int] = {}
    for c in cases:
        if not c.correct:
            error_types[c.error_type] = error_types.get(c.error_type, 0) + 1
    extras = {"per_field": per_field[:100], "invalid_expected_json": invalid_expected, "criterion": cfg.criterion, "error_types": error_types}
    return EvaluationOutcome("json", cases, metrics, "accuracy", acc, extras)
