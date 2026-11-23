"""Orchestrates an investigation: evidence package -> LLM -> validation -> persistence."""
from __future__ import annotations

import json
import logging
from datetime import datetime, time as dtime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ValidationFailed
from app.evidence.package import EvidencePackage, build_package
from app.investigator import providers
from app.investigator.schemas import INSUFFICIENT_EVIDENCE, InvestigationReport, openai_strict_schema
from app.investigator.validation import validate_report
from app.models import EvaluationRun, EvidenceItem, Experiment, FailureGroup, Investigation, InvestigationHypothesis
from app.services.activity import log_activity

log = logging.getLogger(__name__)
PROMPTS = Path(__file__).resolve().parents[1] / "prompts"
MIN_FAILURES = 5
MAX_FOCUS_GROUPS = 4


def load_prompt(name: str) -> str:
    return (PROMPTS / name).read_text(encoding="utf-8")


def _neutralise(text: str) -> str:
    # Data must not be able to close the evidence block or open a new one.
    return text.replace("</evidence_package", "</evidence_package_").replace("<evidence_package", "<evidence_package_")


def build_prompts(run: EvaluationRun, pkg: EvidencePackage) -> tuple[str, str]:
    project = run.project
    evidence_json = _neutralise(json.dumps([{k: v for k, v in i.items() if k != "record_index"} for i in pkg.items], ensure_ascii=False, indent=1))
    user = load_prompt("investigator_user.md").format(
        project_name=_neutralise(project.name), model_category=project.model_category, task_type=run.task_type, run_id=run.id,
        synthetic_note="Note: this run uses a SYNTHETIC benchmark dataset with planted failure patterns.\n" if run.dataset.is_synthetic else "",
        evidence_json=evidence_json, evidence_ids=", ".join(sorted(pkg.ids)), group_keys=", ".join(pkg.groups) or "(none)",
        max_hypotheses=4, max_experiments=3,
    )
    return load_prompt("investigator_system.md"), user


def spent_today(db: Session) -> float:
    start = datetime.combine(datetime.now(timezone.utc).date(), dtime.min, tzinfo=timezone.utc)
    return float(db.scalar(select(func.coalesce(func.sum(Investigation.cost_usd), 0.0)).where(Investigation.created_at >= start)) or 0.0)


def _select_groups(run: EvaluationRun, ids: list[int] | None) -> list[FailureGroup]:
    if ids:
        by_id = {g.id: g for g in run.failure_groups}
        missing = [i for i in ids if i not in by_id]
        if missing:
            raise ValidationFailed(f"Failure group(s) {missing} do not belong to run {run.id}.")
        return [by_id[i] for i in ids][:MAX_FOCUS_GROUPS]
    reliable = [g for g in run.failure_groups if g.reliability == "reliable"]
    return reliable[:MAX_FOCUS_GROUPS]


def run_investigation(db: Session, run: EvaluationRun, focus_group_ids: list[int] | None = None, model: str | None = None) -> Investigation:
    if run.status != "completed":
        raise ValidationFailed("This evaluation run did not complete, so it cannot be investigated.")
    settings = get_settings()
    project = run.project
    groups = _select_groups(run, focus_group_ids)
    inv = Investigation(project_id=project.id, run_id=run.id, status="pending", focus_group_ids=[g.id for g in groups],
                        provider=settings.llm_provider, model=model or settings.llm_model)
    db.add(inv)
    db.flush()

    pkg = build_package(run, groups)
    for item in pkg.items:
        inv.evidence.append(EvidenceItem(evidence_key=item["evidence_id"], kind=item["kind"], title=item["title"][:300],
                                         record_index=item["record_index"], content=item["content"]))
    inv.validation = {"evidence_count": len(pkg.items), "groups": pkg.groups}

    def finish(status: str, message: str) -> Investigation:
        inv.status, inv.message = status, message
        log_activity(db, "investigation", f"Investigation #{inv.id} on run #{run.id}: {status.replace('_', ' ')}.", project.id, f"/investigations/{inv.id}")
        db.commit()
        db.refresh(inv)
        return inv

    # Deterministic gates: never call the LLM when the answer is already known.
    if run.failure_count < MIN_FAILURES or not groups:
        inv.report = {"sufficient_evidence": False, "summary": INSUFFICIENT_EVIDENCE, "hypotheses": [], "experiments": [], "limitations": [
            f"{run.failure_count} failures and {len([g for g in run.failure_groups if g.reliability == 'reliable'])} reliable failure groups were found."]}
        return finish("insufficient_evidence", INSUFFICIENT_EVIDENCE)
    if not project.llm_investigation_enabled:
        return finish("llm_disabled", "LLM investigation is turned off for this project, so no data was sent to an LLM. "
                      "The evidence package below was built from the deterministic analysis. Turn on LLM investigation in the project settings to generate hypotheses.")
    if not settings.llm_configured:
        return finish("llm_not_configured", "No LLM API key is configured on the server (OPENAI_API_KEY or LLM_API_KEY). "
                      "Statistical analysis and evidence are still available; AI hypotheses need a key.")
    if settings.llm_daily_budget_usd > 0 and spent_today(db) >= settings.llm_daily_budget_usd:
        return finish("budget_exceeded", f"The daily LLM budget (${settings.llm_daily_budget_usd:.2f}) has been reached. Try again tomorrow or raise LLM_DAILY_BUDGET_USD.")

    system, user = build_prompts(run, pkg)
    schema = openai_strict_schema()
    try:
        provider = providers.get_provider(model)
    except providers.LLMError as e:
        return finish("llm_not_configured", e.message)

    report: InvestigationReport | None = None
    error_note = ""
    for attempt in range(2):  # one repair attempt if the output does not match the schema
        prompt = user if attempt == 0 else user + f"\n\nYour previous answer did not match the schema ({error_note}). Return a corrected JSON object only."
        try:
            resp = provider.complete_json(system, prompt, "investigation_report", schema)
        except providers.LLMError as e:
            log.warning("Investigation %s LLM error: %s", inv.id, e.message)
            return finish("llm_error", e.message)
        inv.prompt_tokens += resp.prompt_tokens
        inv.completion_tokens += resp.completion_tokens
        inv.cost_usd = providers.estimate_cost(inv.prompt_tokens, inv.completion_tokens)
        inv.latency_ms = (inv.latency_ms or 0) + resp.latency_ms
        inv.attempts += resp.attempts
        inv.model = resp.model
        try:
            report = InvestigationReport.model_validate_json(resp.text)
            break
        except ValidationError as e:
            error_note = "; ".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors()[:5])
            log.warning("Investigation %s: schema validation failed: %s", inv.id, error_note)
    if report is None:
        inv.validation = {**inv.validation, "schema_errors": error_note}
        return finish("invalid_output", "The LLM's answer did not match the required report format twice, so it was discarded. No report was generated.")

    data, validation = validate_report(report, pkg)
    inv.report = data
    inv.validation = {**inv.validation, **validation}
    for rank, h in enumerate(data["hypotheses"], 1):
        inv.hypotheses.append(InvestigationHypothesis(
            rank=rank, title=h["title"][:300], statement=h["explanation"], evidence_level="hypothesis", confidence=h["confidence"],
            supporting_evidence=[r["evidence_id"] for r in h["supporting_evidence"]], counter_evidence=[r["evidence_id"] for r in h["counter_evidence"]],
            invalid_references=h.get("invalid_references", []), validation_status=h["validation_status"]))
    group_by_id = {g.id: g for g in run.failure_groups}
    for e in data["experiments"]:
        g = group_by_id.get(e["failure_group_id"])
        db.add(Experiment(
            project_id=project.id, investigation_id=inv.id, failure_group_id=g.id if g else None, baseline_run_id=run.id,
            title=e["title"][:300], target_failure_group=g.name if g else e["target_group"], hypothesis=e["hypothesis"],
            proposed_change=e["proposed_change"], test_procedure=e["test_procedure"],
            baseline_metric_name=f"Error rate in failure group: {g.name}" if g else e["measurement"],
            baseline_metric_value=g.error_rate if g else None,  # measured by the engine, never taken from the LLM
            success_criterion=e["success_criterion"], risks=e["risks"], evidence_refs=e["evidence_ids"], status="recommended",
            source="investigator", notes=f"Suggested measurement: {e['measurement']}\nExpected outcome (unverified): {e['expected_outcome']}"))
    status = "insufficient_evidence" if validation["status"] == "insufficient_evidence" else validation["status"]
    return finish(status, INSUFFICIENT_EVIDENCE if status == "insufficient_evidence" else "Report generated and checked against the evidence package.")


def investigation_payload(inv: Investigation) -> dict[str, Any]:
    return {
        "id": inv.id, "project_id": inv.project_id, "run_id": inv.run_id, "status": inv.status, "message": inv.message,
        "provider": inv.provider, "model": inv.model, "focus_group_ids": inv.focus_group_ids, "report": inv.report,
        "validation": inv.validation, "prompt_tokens": inv.prompt_tokens, "completion_tokens": inv.completion_tokens,
        "cost_usd": inv.cost_usd, "latency_ms": inv.latency_ms, "attempts": inv.attempts, "created_at": inv.created_at,
        "evidence_count": len(inv.evidence),
        "hypotheses": [{"rank": h.rank, "title": h.title, "statement": h.statement, "evidence_level": h.evidence_level, "confidence": h.confidence,
                        "supporting_evidence": h.supporting_evidence, "counter_evidence": h.counter_evidence,
                        "invalid_references": h.invalid_references, "validation_status": h.validation_status} for h in inv.hypotheses],
    }
