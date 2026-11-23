"""Feature table for failure discovery.

Columns come from two places:
* metadata columns the user mapped (categorical, boolean or numeric), and
* features derived from the input / expected text (length, date mentions, script, formatting).

Nothing is derived from the *actual* model output: such features would trivially predict
failure (leakage) and say nothing about which inputs are hard.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

MISSING = "(missing)"
MAX_CATEGORIES = 30

_MONTHS = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_HINDI_MONTHS = r"(?:जनवरी|फ़रवरी|फरवरी|मार्च|अप्रैल|मई|जून|जुलाई|अगस्त|सितंबर|सितम्बर|अक्टूबर|अक्तूबर|नवंबर|नवम्बर|दिसंबर|दिसम्बर)"
DATE_PATTERN = re.compile(
    rf"\b\d{{4}}-\d{{1,2}}-\d{{1,2}}\b"
    rf"|\b\d{{1,2}}[/.-]\d{{1,2}}[/.-]\d{{2,4}}\b"
    rf"|\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?{_MONTHS}\b\.?(?:,?\s+\d{{4}})?"
    rf"|\b{_MONTHS}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?"
    rf"|\d{{1,2}}\s+{_HINDI_MONTHS}(?:\s+\d{{4}})?",
    re.IGNORECASE,
)
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_LATIN = re.compile(r"[A-Za-z]")
_NUMBER = re.compile(r"\b\d+(?:[.,]\d+)?\b")


def count_dates(text: str) -> int:
    return len(DATE_PATTERN.findall(text or ""))


def detect_script(text: str) -> str:
    dev = len(_DEVANAGARI.findall(text or ""))
    lat = len(_LATIN.findall(text or ""))
    total = dev + lat
    if total == 0:
        return "none"
    if dev / total > 0.6:
        return "devanagari"
    if lat / total > 0.85:
        return "latin"
    return "mixed"


def formatting_style(text: str) -> str:
    t = text or ""
    if t.count("|") >= 4 or t.count("\t") >= 3:
        return "table_like"
    letters = [c for c in t if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) / len(letters) > 0.6 and len(letters) > 20:
        return "mostly_uppercase"
    if t.count("\n") >= 8 or re.search(r"(?m)^\s*[-*•]\s", t):
        return "list_or_multiline"
    return "plain"


@dataclass
class FeatureSpec:
    name: str
    kind: str          # categorical | numeric
    origin: str        # metadata | derived
    description: str = ""


@dataclass
class FeatureFrame:
    frame: pd.DataFrame                   # one row per evaluated case (aligned with `failures`)
    specs: dict[str, FeatureSpec]
    excluded: list[dict[str, str]] = field(default_factory=list)


def _as_numeric(values: list[Any]) -> pd.Series | None:
    s = pd.to_numeric(pd.Series(values, dtype="object"), errors="coerce")
    present = sum(v is not None for v in values)
    if present == 0:
        return None
    if s.notna().sum() / present >= 0.95:
        return s.astype(float)
    return None


def derive_text_features(inputs: list[str | None], expected: list[str | None]) -> dict[str, tuple[list[Any], FeatureSpec]]:
    feats: dict[str, tuple[list[Any], FeatureSpec]] = {}
    if any(inputs):
        texts = [t or "" for t in inputs]
        feats["input_length_words"] = ([len(t.split()) for t in texts], FeatureSpec("input_length_words", "numeric", "derived", "number of words in the input"))
        feats["date_mentions"] = ([count_dates(t) for t in texts], FeatureSpec("date_mentions", "numeric", "derived", "dates detected in the input"))
        feats["number_mentions"] = ([len(_NUMBER.findall(t)) for t in texts], FeatureSpec("number_mentions", "numeric", "derived", "numbers detected in the input"))
        feats["input_script"] = ([detect_script(t) for t in texts], FeatureSpec("input_script", "categorical", "derived", "dominant writing system of the input"))
        feats["input_format"] = ([formatting_style(t) for t in texts], FeatureSpec("input_format", "categorical", "derived", "layout of the input text"))
    if any(expected):
        feats["expected_length_words"] = ([len((t or "").split()) for t in expected], FeatureSpec("expected_length_words", "numeric", "derived", "words in the expected output"))
    return feats


def build_feature_frame(
    records: list[dict[str, Any]],
    case_indices: list[int],
    mapping: dict[str, Any],
    *,
    derive: bool = True,
    extra_categorical: dict[str, list[Any]] | None = None,
) -> FeatureFrame:
    rows = [records[i] for i in case_indices]
    n = len(rows)
    data: dict[str, list[Any]] = {}
    specs: dict[str, FeatureSpec] = {}
    excluded: list[dict[str, str]] = []

    for col in mapping.get("metadata_columns", []) or []:
        values = [r.get(col) for r in rows]
        present = [v for v in values if v is not None]
        uniq = set(present)
        if not present:
            excluded.append({"feature": col, "reason": "all values missing"})
            continue
        if len(uniq) <= 1 and len(present) == n:
            excluded.append({"feature": col, "reason": "constant value"})
            continue
        num = _as_numeric(values)
        lname = col.lower()
        if lname in ("id", "uuid", "uid", "case_id", "row", "index") or lname.endswith("_id"):
            excluded.append({"feature": col, "reason": "identifier column"})
            continue
        if num is not None and len(uniq) == n and n >= 20:
            vals = num.dropna()
            if bool((vals % 1 == 0).all()) and vals.max() - vals.min() + 1 == n:
                excluded.append({"feature": col, "reason": "identifier-like (a running number)"})
                continue
        if num is not None and len(uniq) > 2:
            data[col] = num.tolist()
            specs[col] = FeatureSpec(col, "numeric", "metadata")
            continue
        if len(uniq) >= 0.9 * n and n >= 20:
            excluded.append({"feature": col, "reason": "identifier-like (almost every value is unique)"})
            continue
        data[col] = [v if v is not None else MISSING for v in values]
        specs[col] = FeatureSpec(col, "categorical", "metadata")

    if derive:
        inp_col = mapping.get("input_column")
        inputs = [r.get(inp_col) for r in rows] if inp_col else [None] * n
        expected = [r.get(mapping["expected_column"]) for r in rows]
        for name, (vals, spec) in derive_text_features(inputs, expected).items():
            if name in data:
                continue
            if len(set(vals)) <= 1:
                continue
            data[name] = vals
            specs[name] = spec

    for name, vals in (extra_categorical or {}).items():
        if len(set(vals)) > 1:
            data[name] = vals
            specs[name] = FeatureSpec(name, "categorical", "derived", "ground-truth class")

    frame = pd.DataFrame(data, index=range(n))
    # Cap categorical cardinality: keep the most frequent values, fold the rest into "(other)".
    for name, spec in specs.items():
        if spec.kind == "categorical":
            vc = frame[name].astype(str).value_counts()
            if len(vc) > MAX_CATEGORIES:
                keep = set(vc.index[:MAX_CATEGORIES])
                frame[name] = frame[name].astype(str).where(frame[name].astype(str).isin(keep), "(other)")
            else:
                frame[name] = frame[name].astype(str)
    return FeatureFrame(frame, specs, excluded)


def fmt_num(x: float) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "?"
    return f"{x:,.0f}" if float(x).is_integer() or abs(x) >= 100 else f"{x:,.2f}"


def condition_label(c: dict[str, Any]) -> str:
    f, op = c["feature"], c["op"]
    if op == "==":
        return f"{f} = {c['value']}"
    if op == "!=":
        return f"{f} ≠ {c['value']}"
    if op == "between":
        lo, hi = c.get("low"), c.get("high")
        if lo is None:
            return f"{f} < {fmt_num(hi)}"
        if hi is None:
            return f"{f} ≥ {fmt_num(lo)}"
        return f"{fmt_num(lo)} ≤ {f} < {fmt_num(hi)}"
    if op == "is_missing":
        return f"{f} is missing"
    return f"{f} {op} {c.get('value')}"


def rule_text(conditions: list[dict[str, Any]]) -> str:
    return "\nAND\n".join(condition_label(c) for c in conditions)


def apply_conditions(frame: pd.DataFrame, conditions: list[dict[str, Any]]) -> np.ndarray:
    """Boolean mask of rows matching every condition. Unknown features match nothing."""
    mask = np.ones(len(frame), dtype=bool)
    for c in conditions:
        f = c["feature"]
        if f not in frame.columns:
            return np.zeros(len(frame), dtype=bool)
        col = frame[f]
        op = c["op"]
        if op == "==":
            mask &= (col.astype(str) == str(c["value"])).to_numpy()
        elif op == "!=":
            mask &= (col.astype(str) != str(c["value"])).to_numpy()
        elif op == "between":
            num = pd.to_numeric(col, errors="coerce")
            m = num.notna()
            if c.get("low") is not None:
                m &= num >= c["low"]
            if c.get("high") is not None:
                m &= num < c["high"]
            mask &= m.to_numpy()
        elif op == "is_missing":
            mask &= (col.isna() | (col.astype(str) == MISSING)).to_numpy()
        else:
            return np.zeros(len(frame), dtype=bool)
    return mask
