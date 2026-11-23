"""Workspace-level endpoints: overview dashboard, activity feed, search and public settings."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import get_db
from app.evaluation.similarity import embeddings_available
from app.investigator.service import spent_today
from app.models import ActivityEvent, Dataset, EvaluationRun, Experiment, FailureGroup, Investigation, Project

router = APIRouter(tags=["workspace"])


@router.get("/overview")
def overview(project_id: int | None = None, db: Session = Depends(get_db)) -> dict:
    def scoped(stmt, model):
        return stmt.where(model.project_id == project_id) if project_id is not None else stmt

    runs = db.scalars(scoped(select(EvaluationRun), EvaluationRun).where(EvaluationRun.status == "completed").order_by(EvaluationRun.created_at)).all()
    latest = runs[-1] if runs else None
    group_counts = dict(db.execute(select(FailureGroup.run_id, func.count(FailureGroup.id)).group_by(FailureGroup.run_id)).all())
    investigations = db.scalars(scoped(select(Investigation), Investigation)).all()
    exp_status = dict(db.execute(scoped(select(Experiment.status, func.count(Experiment.id)), Experiment).group_by(Experiment.status)).all())
    projects_q = select(func.count(Project.id)) if project_id is None else select(func.count(Project.id)).where(Project.id == project_id)
    demo_q = select(func.count(Project.id)).where(Project.is_demo.is_(True))
    if project_id is not None:
        demo_q = demo_q.where(Project.id == project_id)
    demo_projects = db.scalar(demo_q) or 0
    error_types: dict[str, int] = {}
    if latest:
        for c in latest.case_results:
            if not c["correct"]:
                error_types[c["error_type"] or "other"] = error_types.get(c["error_type"] or "other", 0) + 1
    return {
        "projects": db.scalar(projects_q) or 0,
        "demo_projects": demo_projects,
        "datasets": db.scalar(scoped(select(func.count(Dataset.id)), Dataset)) or 0,
        "evaluation_runs": len(runs),
        "failure_groups": sum(group_counts.get(r.id, 0) for r in runs),
        "reliable_failure_groups": db.scalar(select(func.count(FailureGroup.id)).where(FailureGroup.run_id.in_([r.id for r in runs]), FailureGroup.reliability == "reliable")) or 0 if runs else 0,
        "investigations_completed": sum(1 for i in investigations if i.status in ("completed", "completed_with_warnings")),
        "investigations_total": len(investigations),
        "experiments": exp_status,
        "pending_experiments": sum(v for k, v in exp_status.items() if k in ("recommended", "planned", "running")),
        "latest_run": None if not latest else {
            "id": latest.id, "project_id": latest.project_id, "project_name": latest.project.name, "label": latest.label, "task_type": latest.task_type,
            "error_rate": latest.error_rate, "headline_metric": latest.headline_metric, "headline_value": latest.headline_value,
            "failure_groups": group_counts.get(latest.id, 0), "created_at": latest.created_at, "synthetic": latest.dataset.is_synthetic,
            "analysis_status": latest.analysis_status,
        },
        "trend": [{"run_id": r.id, "label": r.label, "project": r.project.name, "created_at": r.created_at, "error_rate": r.error_rate,
                   "headline_value": r.headline_value, "failure_groups": group_counts.get(r.id, 0), "synthetic": r.dataset.is_synthetic} for r in runs[-20:]],
        "latest_error_types": error_types,
        "latest_groups": [] if not latest else [{"id": g.id, "name": g.name, "error_rate": g.error_rate, "baseline": g.baseline_error_rate,
                                                 "records": g.sample_size, "reliability": g.reliability, "severity": g.severity} for g in latest.failure_groups[:8]],
    }


@router.get("/activity")
def activity(limit: int = Query(20, ge=1, le=100), project_id: int | None = None, db: Session = Depends(get_db)) -> list[dict]:
    stmt = select(ActivityEvent)
    if project_id is not None:
        stmt = stmt.where(ActivityEvent.project_id == project_id)
    rows = db.scalars(stmt.order_by(ActivityEvent.created_at.desc(), ActivityEvent.id.desc()).limit(limit)).all()
    return [{"id": a.id, "kind": a.kind, "message": a.message, "link": a.link, "project_id": a.project_id, "created_at": a.created_at} for a in rows]


@router.get("/search")
def search(q: str = Query(..., min_length=1, max_length=100), db: Session = Depends(get_db)) -> list[dict]:
    like = f"%{q}%"
    out: list[dict] = []
    for p in db.scalars(select(Project).where(Project.name.ilike(like)).limit(5)):
        out.append({"type": "project", "title": p.name, "subtitle": p.model_category.replace("_", " "), "link": f"/projects/{p.id}"})
    for d in db.scalars(select(Dataset).where(Dataset.name.ilike(like)).limit(5)):
        out.append({"type": "dataset", "title": f"{d.name} v{d.version}", "subtitle": f"{d.row_count:,} records", "link": f"/datasets/{d.id}"})
    for g in db.scalars(select(FailureGroup).where(FailureGroup.name.ilike(like)).order_by(FailureGroup.id.desc()).limit(5)):
        out.append({"type": "failure_group", "title": g.name, "subtitle": f"run #{g.run_id} · {g.error_rate:.0%} error rate", "link": f"/failures?run={g.run_id}&group={g.id}"})
    for e in db.scalars(select(Experiment).where(Experiment.title.ilike(like)).limit(5)):
        out.append({"type": "experiment", "title": e.title, "subtitle": e.status, "link": f"/experiments?focus={e.id}"})
    return out


@router.get("/settings")
def public_settings(db: Session = Depends(get_db)) -> dict:
    s = get_settings()
    return {
        "llm": {"configured": s.llm_configured, "provider": s.llm_provider, "model": s.llm_model,
                "base_url": s.llm_base_url if s.llm_provider != "openai" else "https://api.openai.com/v1",
                "timeout_seconds": s.llm_timeout_seconds, "max_retries": s.llm_max_retries,
                "price_per_million_tokens": {"input": s.llm_input_price_per_m, "output": s.llm_output_price_per_m},
                "daily_budget_usd": s.llm_daily_budget_usd, "spent_today_usd": round(spent_today(db), 4)},
        "limits": {"max_upload_mb": s.max_upload_mb, "max_rows": s.max_rows},
        "retention_days": s.retention_days,
        "analysis": {"min_group_size": s.min_group_size, "fdr_alpha": s.fdr_alpha, "embeddings_available": embeddings_available()},
        "environment": s.environment,
    }
