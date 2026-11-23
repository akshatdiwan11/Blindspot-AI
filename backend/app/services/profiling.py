"""Dataset profiling: column types, missing values, duplicates, invalid records."""
from __future__ import annotations

import json
from collections import Counter
from typing import Any

BOOL_VALUES = {"true", "false", "yes", "no", "y", "n", "t", "f"}


def _is_float(v: str) -> bool:
    try:
        float(v)
    except ValueError:
        return False
    return v.strip().lower() not in ("nan", "inf", "-inf", "infinity")


def infer_dtype(values: list[str]) -> str:
    if not values:
        return "empty"
    sample = values[:2000]
    low = [v.strip().lower() for v in sample]
    if all(v in BOOL_VALUES for v in low):
        return "boolean"
    if all(_is_float(v.strip()) for v in sample):
        return "numeric"
    if all(v.strip()[:1] in "{[" for v in sample):
        try:
            for v in sample[:200]:
                json.loads(v)
            return "json"
        except json.JSONDecodeError:
            pass
    avg_len = sum(len(v) for v in sample) / len(sample)
    unique_ratio = len(set(sample)) / len(sample)
    if avg_len > 40 or (unique_ratio > 0.5 and len(set(sample)) > 50):
        return "text"
    return "categorical"


def profile_columns(columns: list[str], rows: list[dict[str, str | None]]) -> list[dict[str, Any]]:
    out = []
    n = len(rows)
    for c in columns:
        vals = [r.get(c) for r in rows]
        present = [v for v in vals if v is not None]
        counts = Counter(present)
        out.append({
            "name": c,
            "dtype": infer_dtype(present),
            "missing": n - len(present),
            "missing_pct": round((n - len(present)) / n, 4) if n else 0.0,
            "unique": len(counts),
            "top_values": [{"value": v[:80], "count": k} for v, k in counts.most_common(5)],
            "avg_length": round(sum(len(v) for v in present) / len(present), 1) if present else 0,
        })
    return out


def count_duplicates(rows: list[dict[str, str | None]], columns: list[str], exclude: set[str] | None = None) -> int:
    """Rows that are exact duplicates of an earlier row (ignoring id-like columns in `exclude`)."""
    keys = [c for c in columns if not exclude or c not in exclude]
    seen: set[tuple] = set()
    dupes = 0
    for r in rows:
        k = tuple(r.get(c) for c in keys)
        if k in seen:
            dupes += 1
        else:
            seen.add(k)
    return dupes


def guess_mapping(columns: list[dict[str, Any]]) -> dict[str, Any]:
    """Suggest a column mapping from common header names. The user always confirms it."""
    names = [c["name"] for c in columns]
    lower = {n.lower(): n for n in names}

    def pick(*cands: str) -> str | None:
        for cand in cands:
            if cand in lower:
                return lower[cand]
        for cand in cands:
            for ln, orig in lower.items():
                if cand in ln:
                    return orig
        return None

    mapping = {
        "input_column": pick("input_text", "input", "question", "prompt", "context", "text", "document"),
        "expected_column": pick("expected_output", "expected", "ground_truth", "label", "reference", "target", "gold"),
        "actual_column": pick("actual_output", "actual", "prediction", "predicted", "model_output", "output", "response"),
        "case_id_column": pick("case_id", "id", "uid", "example_id"),
    }
    used = {v for v in mapping.values() if v}
    mapping["metadata_columns"] = [
        c["name"] for c in columns if c["name"] not in used and c["dtype"] in ("categorical", "boolean", "numeric") and c["unique"] > 1
    ]
    return mapping


def build_profile(columns: list[str], rows: list[dict[str, str | None]], invalid_rows: list[dict[str, Any]], warnings: list[str]) -> dict[str, Any]:
    col_profiles = profile_columns(columns, rows)
    id_like = {c["name"] for c in col_profiles if c["unique"] == len(rows) and c["name"].lower() in ("id", "case_id", "uid", "example_id")}
    return {
        "total_records": len(rows),
        "total_columns": len(columns),
        "missing_values": sum(c["missing"] for c in col_profiles),
        "duplicate_records": count_duplicates(rows, columns, exclude=id_like),
        "invalid_records": len(invalid_rows),
        "invalid_rows": invalid_rows[:100],
        "columns": col_profiles,
        "warnings": warnings,
        "suggested_mapping": guess_mapping(col_profiles),
    }


def validate_mapping_against(rows: list[dict[str, str | None]], mapping: dict[str, Any]) -> dict[str, Any]:
    """Row-level checks once the user has mapped columns."""
    exp, act, inp, cid = mapping["expected_column"], mapping["actual_column"], mapping.get("input_column"), mapping.get("case_id_column")
    missing_expected = [i for i, r in enumerate(rows) if r.get(exp) is None]
    missing_actual = [i for i, r in enumerate(rows) if r.get(act) is None]
    missing_input = [i for i, r in enumerate(rows) if inp and r.get(inp) is None]
    dup_ids: list[str] = []
    if cid:
        counts = Counter(r.get(cid) for r in rows if r.get(cid) is not None)
        dup_ids = [k for k, v in counts.items() if v > 1]
    warnings = []
    if missing_actual:
        warnings.append(f"{len(missing_actual)} record(s) have no actual output. They are evaluated as empty outputs (counted as failures).")
    if missing_expected:
        warnings.append(f"{len(missing_expected)} record(s) have no expected output and will be excluded from evaluation.")
    if dup_ids:
        warnings.append(f"{len(dup_ids)} case ID(s) appear more than once. Row numbers will be used to tell them apart.")
    leaks = []
    for m in mapping.get("metadata_columns", []):
        same_as = [name for name, col in (("expected output", exp), ("actual output", act)) if all(r.get(m) == r.get(col) for r in rows)]
        if same_as:
            leaks.append(m)
            warnings.append(f"Metadata column '{m}' is identical to the {same_as[0]} and was removed to avoid leakage.")
    return {
        "valid_records": len(rows) - len(missing_expected),
        "excluded_records": len(missing_expected),
        "missing_actual": len(missing_actual),
        "missing_input": len(missing_input),
        "duplicate_case_ids": len(dup_ids),
        "leaky_metadata_columns": leaks,
        "warnings": warnings,
    }
