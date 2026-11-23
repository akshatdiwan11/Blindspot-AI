"""Post-hoc validation of the LLM report against the evidence package.

* Evidence IDs and group keys must exist in the package; unknown ones are removed and recorded.
* A hypothesis left with no valid supporting evidence is flagged as unsupported.
* Numbers quoted in the text must appear somewhere in the package (rounding tolerated).
* Overclaiming language ("proves", "definitely causes") is flagged.
"""
from __future__ import annotations

import re
from typing import Any

from app.evidence.package import EvidencePackage
from app.investigator.schemas import INSUFFICIENT_EVIDENCE, InvestigationReport

_ID = re.compile(r"\bEVIDENCE_\d{3}\b")
_GROUP = re.compile(r"\bGROUP_\d+\b")
_NUM = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(%|percent|percentage points|pp)?", re.IGNORECASE)
_OVERCLAIM = re.compile(r"\b(proves?|proven|definitely|certainly|undoubtedly|the root cause is|is caused by|guarantee[sd]?)\b", re.IGNORECASE)


def _number_known(value: float, is_pct: bool, known: set[float]) -> bool:
    tol = 0.6 if is_pct else 0.01
    return any(abs(value - k) <= max(tol, abs(k) * 0.005) for k in known)


def _texts(report: InvestigationReport) -> list[tuple[str, str]]:
    out = [("summary", report.summary)]
    if report.main_pattern:
        out.append(("main_pattern", report.main_pattern.description))
    for i, h in enumerate(report.hypotheses, 1):
        out += [(f"hypothesis {i}", h.title), (f"hypothesis {i}", h.explanation)]
        out += [(f"hypothesis {i} evidence", r.explanation) for r in h.supporting_evidence + h.counter_evidence]
    if report.assessment:
        out.append(("assessment", report.assessment.rationale))
    for i, e in enumerate(report.experiments, 1):
        out += [(f"experiment {i}", e.hypothesis), (f"experiment {i}", e.expected_outcome), (f"experiment {i}", e.success_criterion)]
    return out


def validate_report(report: InvestigationReport, pkg: EvidencePackage) -> tuple[dict[str, Any], dict[str, Any]]:
    valid_ids, valid_groups = pkg.ids, set(pkg.groups)
    issues: list[dict[str, Any]] = []
    invalid_refs: set[str] = set()
    data = report.model_dump()

    if not report.sufficient_evidence:
        data.update({"summary": INSUFFICIENT_EVIDENCE, "hypotheses": [], "experiments": []})
        return data, {"status": "insufficient_evidence", "issues": [], "invalid_references": [], "unverified_numbers": [], "flagged_hypotheses": 0}

    def keep_ids(ids: list[str], where: str) -> list[str]:
        good = []
        for i in ids:
            if i in valid_ids:
                good.append(i)
            else:
                invalid_refs.add(i)
                issues.append({"severity": "error", "where": where, "message": f"Reference '{i}' is not in the evidence package and was removed."})
        return good

    def keep_groups(gs: list[str], where: str) -> list[str]:
        good = []
        for g in gs:
            if g in valid_groups:
                good.append(g)
            else:
                invalid_refs.add(g)
                issues.append({"severity": "error", "where": where, "message": f"Failure group '{g}' does not exist and was removed."})
        return good

    if data["main_pattern"]:
        mp = data["main_pattern"]
        mp["evidence_ids"] = keep_ids(mp["evidence_ids"], "main pattern")
        mp["failure_groups"] = keep_groups(mp["failure_groups"], "main pattern")

    flagged = 0
    for i, h in enumerate(data["hypotheses"], 1):
        where = f"hypothesis {i}"
        h_invalid_before = set(invalid_refs)
        h["supporting_evidence"] = [r for r in h["supporting_evidence"] if keep_ids([r["evidence_id"]], where)]
        h["counter_evidence"] = [r for r in h["counter_evidence"] if keep_ids([r["evidence_id"]], where)]
        h["related_groups"] = keep_groups(h["related_groups"], where)
        h["invalid_references"] = sorted(invalid_refs - h_invalid_before)
        status = "valid"
        if not h["supporting_evidence"]:
            status = "flagged"
            issues.append({"severity": "error", "where": where, "message": "No valid supporting evidence: this hypothesis is unsupported."})
        elif h["invalid_references"]:
            status = "flagged"
        if _OVERCLAIM.search(h["title"] + " " + h["explanation"]):
            status = "flagged"
            issues.append({"severity": "warning", "where": where, "message": "Uses causal certainty language; treat as an untested hypothesis."})
        h["validation_status"] = status
        h["evidence_level"] = "hypothesis"
        flagged += status == "flagged"

    kept_experiments = []
    for i, e in enumerate(data["experiments"], 1):
        where = f"experiment {i}"
        e["evidence_ids"] = keep_ids(e["evidence_ids"], where)
        if e["target_group"] not in valid_groups:
            invalid_refs.add(e["target_group"])
            issues.append({"severity": "error", "where": where, "message": f"Targets unknown failure group '{e['target_group']}'; the experiment was dropped."})
            continue
        e["failure_group_id"] = pkg.groups[e["target_group"]]
        kept_experiments.append(e)
    data["experiments"] = kept_experiments

    # Free-text references to IDs that do not exist.
    for where, text in _texts(report):
        for ref in set(_ID.findall(text or "")) - valid_ids:
            invalid_refs.add(ref)
            issues.append({"severity": "error", "where": where, "message": f"Text mentions '{ref}', which is not in the evidence package."})
        for ref in set(_GROUP.findall(text or "")) - valid_groups:
            invalid_refs.add(ref)
            issues.append({"severity": "error", "where": where, "message": f"Text mentions '{ref}', which does not exist."})

    unverified: list[str] = []
    for where, text in _texts(report):
        cleaned = _ID.sub(" ", _GROUP.sub(" ", text or ""))
        for m in _NUM.finditer(cleaned):
            value, unit = float(m.group(1)), (m.group(2) or "")
            if value in (0, 1, 2, 3, 4, 5) and not unit:
                continue  # small counts like "two hypotheses" / list numbering
            if 1900 <= value <= 2100 and not unit:
                continue  # years in quoted dates
            if not _number_known(value, bool(unit), pkg.numbers):
                unverified.append(f"{m.group(0).strip()} ({where})")
    if unverified:
        issues.append({"severity": "warning", "where": "report", "message": f"{len(unverified)} number(s) in the text do not match any value in the evidence package."})

    status = "completed" if not issues else "completed_with_warnings"
    return data, {"status": status, "issues": issues, "invalid_references": sorted(invalid_refs),
                  "unverified_numbers": unverified[:20], "flagged_hypotheses": flagged}
