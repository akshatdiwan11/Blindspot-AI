"""Builds the evidence package handed to the AI investigator.

Every item gets a stable ID (EVIDENCE_001, ...). Items are either verified statistics computed
by the engine or verbatim records from the dataset. The investigator may only cite these IDs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.evidence.retrieval import CaseIndex, case_text
from app.models import EvaluationRun, FailureGroup
from app.services.cases import build_case, case_lookup

MAX_ITEMS = 45
EXCERPT_CHARS = 700


@dataclass
class EvidencePackage:
    items: list[dict[str, Any]] = field(default_factory=list)
    groups: dict[str, int] = field(default_factory=dict)      # GROUP_1 -> failure_group.id
    numbers: set[float] = field(default_factory=set)          # every number the package states (for claim checking)
    context: dict[str, Any] = field(default_factory=dict)

    def add(self, kind: str, title: str, content: dict[str, Any], record_index: int | None = None) -> str:
        key = f"EVIDENCE_{len(self.items) + 1:03d}"
        self.items.append({"evidence_id": key, "kind": kind, "title": title, "record_index": record_index, "content": content})
        _collect_numbers(content, self.numbers)
        return key

    @property
    def ids(self) -> set[str]:
        return {i["evidence_id"] for i in self.items}


def _collect_numbers(obj: Any, out: set[float]) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        out.add(round(float(obj), 4))
        if 0 <= obj <= 1:
            out.add(round(float(obj) * 100, 1))  # rates are also quoted as percentages
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect_numbers(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _collect_numbers(v, out)


def excerpt(text: str | None, anchors: list[str | None], limit: int = EXCERPT_CHARS) -> str:
    """Start of the text plus windows around the expected / actual answers, so long inputs keep the relevant part."""
    if not text:
        return ""
    if len(text) <= limit:
        return text
    pieces = [text[: limit // 3]]
    low = text.lower()
    for a in anchors:
        if not a:
            continue
        pos = low.find(str(a).lower()[:40])
        if pos > limit // 3:
            pieces.append(text[max(0, pos - 160): pos + 120])
    out = " […] ".join(pieces)
    return out[: limit + 300]


def _case_payload(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": case["case_id"], "outcome": "correct" if case["correct"] else "failed", "error_type": case["error_type"] or None,
        "input_excerpt": excerpt(case["input"], [case["expected"], case["actual"]]),
        "expected_output": (case["expected"] or "")[:500], "actual_output": (case["actual"] or "")[:500],
        "metadata": case["metadata"],
    }


def _pct(x: float | None) -> float | None:
    return None if x is None else round(x * 100, 1)


def build_package(run: EvaluationRun, focus_groups: list[FailureGroup]) -> EvidencePackage:
    ds = run.dataset
    mapping = ds.column_mapping or {}
    lookup = case_lookup(run)
    pkg = EvidencePackage()
    overall = {m.name: m.value for m in run.metrics if m.scope == "overall" and m.value is not None}
    pkg.add("metrics", "Overall evaluation metrics (computed by the evaluation engine)", {
        "task_type": run.task_type, "evaluated_records": run.evaluated_records, "failures": run.failure_count,
        "overall_error_rate_pct": _pct(run.error_rate), "metrics": {k: round(v, 4) for k, v in overall.items()},
    })
    ds_summary = run.discovery_summary or {}
    pkg.add("dataset", "Dataset and analysis context", {
        "dataset": ds.name, "version": ds.version, "synthetic": ds.is_synthetic, "records": ds.row_count,
        "metadata_columns": mapping.get("metadata_columns", []),
        "features_analysed": [f["name"] for f in ds_summary.get("features_used", [])],
        "features_excluded": ds_summary.get("features_excluded", []),
        "analysis_warnings": ds_summary.get("warnings", []),
    })

    positions = [c["index"] for c in run.case_results]
    pos_of = {idx: p for p, idx in enumerate(positions)}
    index = CaseIndex([case_text(ds.records[i], mapping) for i in positions])
    failed_pos = [pos_of[c["index"]] for c in run.case_results if not c["correct"]]
    used: set[int] = set()

    for n, g in enumerate(focus_groups, start=1):
        gkey = f"GROUP_{n}"
        pkg.groups[gkey] = g.id
        pkg.add("subgroup_statistic", f"{gkey} statistics: {g.name}", {
            "group": gkey, "rule": g.rule_text.replace("\n", " "), "records": g.sample_size, "failures": g.failures,
            "error_rate_pct": _pct(g.error_rate), "overall_error_rate_pct": _pct(g.baseline_error_rate),
            "error_rate_outside_group_pct": _pct(g.complement_error_rate), "difference_pct_points": _pct(g.difference),
            "ci95_pct": [_pct(g.ci_low), _pct(g.ci_high)], "q_value": round(g.q_value, 4), "reliability": g.reliability,
            "discovery_method": g.method, "notes": g.notes,
        })
        reps = [e.record_index for e in g.examples if e.is_failure and e.representative][:3]
        for idx in reps:
            c = build_case(ds, run, idx, lookup)
            if c and idx not in used:
                used.add(idx)
                pkg.add("failed_case", f"Representative failure in {gkey} ({c['case_id']})", _case_payload(c), idx)
        oks = [e.record_index for e in g.examples if not e.is_failure][:2]
        for idx in oks:
            c = build_case(ds, run, idx, lookup)
            if c and idx not in used:
                used.add(idx)
                pkg.add("successful_case", f"Correct case inside {gkey} ({c['case_id']}): same rule, but the model succeeded", _case_payload(c), idx)
        # Similar failures *outside* the group: does the weakness extend beyond the rule?
        member_idx = {e.record_index for e in g.examples}
        query = [pos_of[i] for i in reps if i in pos_of]
        outside = [p for p in failed_pos if positions[p] not in member_idx]
        for p, sim in index.nearest(query, outside, 2):
            idx = positions[p]
            c = build_case(ds, run, idx, lookup)
            if c and idx not in used and sim > 0.05:
                used.add(idx)
                pkg.add("similar_failure", f"Failure outside {gkey} that resembles its failures ({c['case_id']})", {**_case_payload(c), "similarity": round(sim, 3)}, idx)
        if len(pkg.items) >= MAX_ITEMS - 6:
            break

    for cl in run.clusters[:4]:
        pkg.add("cluster", f"Failure cluster: {cl.label}", {
            "cluster": cl.cluster_index + 1, "label": cl.label, "failures_in_cluster": cl.size,
            "share_of_all_failures_pct": _pct(cl.share_of_failures), "top_terms": cl.top_terms,
            "dominant_metadata": cl.dominant_metadata, "method": cl.method,
        })
        rep = next((i for i in cl.representative_indices if i not in used), None)
        if rep is not None and len(pkg.items) < MAX_ITEMS:
            c = build_case(ds, run, rep, lookup)
            if c:
                used.add(rep)
                pkg.add("failed_case", f"Representative failure of cluster {cl.cluster_index + 1} ({c['case_id']})", _case_payload(c), rep)
    pkg.context = {"run_id": run.id, "dataset_id": ds.id, "groups": pkg.groups}
    return pkg
