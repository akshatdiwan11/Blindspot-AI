"""Score discovered failure groups against a synthetic benchmark's planted patterns."""
from __future__ import annotations

from typing import Any


def score_recovery(groups: list[dict[str, Any]], labels: list[dict[str, Any]], pattern_ids: list[str],
                   min_precision: float = 0.6, min_recall: float = 0.4) -> dict[str, Any]:
    """`groups`: [{"name", "reliability", "member_case_ids": set}], `labels`: per-case planted flags.

    A planted pattern counts as recovered when some reported *reliable* group's members are
    mostly cases with that pattern (precision) and cover a fair share of them (recall).
    """
    by_pattern: dict[str, Any] = {}
    for pid in pattern_ids:
        planted = {l["case_id"] for l in labels if l.get(pid)}
        best = None
        for g in groups:
            members = g["member_case_ids"]
            if not members or not planted:
                continue
            inter = len(members & planted)
            precision, recall = inter / len(members), inter / len(planted)
            cand = {"group": g["name"], "reliability": g["reliability"], "precision": round(precision, 3), "recall": round(recall, 3)}
            if best is None or (precision * recall) > (best["precision"] * best["recall"]):
                best = cand
        recovered = bool(best and best["reliability"] == "reliable" and best["precision"] >= min_precision and best["recall"] >= min_recall)
        by_pattern[pid] = {"planted_cases": len(planted), "best_match": best, "recovered": recovered}
    return {"patterns": by_pattern, "recovered": sum(v["recovered"] for v in by_pattern.values()), "total": len(pattern_ids)}
