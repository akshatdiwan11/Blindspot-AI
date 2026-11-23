from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import Pagination, experiment_dep, get_or_404
from app.core.errors import ValidationFailed
from app.database.session import get_db
from app.experiments.service import STATUSES, change_status, measure_from_runs, outcome
from app.models import EvaluationRun, Experiment, ExperimentResult, FailureGroup, Project
from app.schemas.common import Page
from app.schemas.experiment import ExperimentCreate, ExperimentOut, ExperimentUpdate, ManualResult, MeasureRequest
from app.services.activity import log_activity

router = APIRouter(prefix="/experiments", tags=["experiments"])


def out(exp: Experiment) -> ExperimentOut:
    o = ExperimentOut.model_validate(exp)
    o.outcome = outcome(exp)
    return o


@router.post("", response_model=ExperimentOut, status_code=status.HTTP_201_CREATED)
def create_experiment(body: ExperimentCreate, db: Session = Depends(get_db)):
    project = get_or_404(db, Project, body.project_id, "Project")
    target, baseline_value, metric_name = "", None, ""
    baseline_run_id = body.baseline_run_id
    if body.failure_group_id is not None:
        g = get_or_404(db, FailureGroup, body.failure_group_id, "Failure group")
        if g.run.project_id != project.id:
            raise ValidationFailed("The failure group belongs to a different project.")
        target, baseline_value, metric_name = g.name, g.error_rate, f"Error rate in failure group: {g.name}"
        baseline_run_id = baseline_run_id or g.run_id
    if baseline_run_id is not None:
        run = get_or_404(db, EvaluationRun, baseline_run_id, "Evaluation run")
        if run.project_id != project.id:
            raise ValidationFailed("The baseline run belongs to a different project.")
        if body.failure_group_id is None:
            metric_name, baseline_value = "Overall error rate", run.error_rate
    exp = Experiment(project_id=project.id, failure_group_id=body.failure_group_id, baseline_run_id=baseline_run_id, title=body.title.strip(),
                     target_failure_group=target, hypothesis=body.hypothesis, proposed_change=body.proposed_change,
                     test_procedure=body.test_procedure, success_criterion=body.success_criterion, risks=body.risks,
                     baseline_metric_name=metric_name, baseline_metric_value=baseline_value, status=body.status, source="manual", notes=body.notes)
    db.add(exp)
    db.flush()
    log_activity(db, "experiment", f"Created experiment '{exp.title}'.", project.id, f"/experiments?focus={exp.id}")
    db.commit()
    db.refresh(exp)
    return out(exp)


@router.get("", response_model=Page[ExperimentOut])
def list_experiments(project_id: int | None = None, status_filter: str | None = Query(None, alias="status"), page: Pagination = Depends(), db: Session = Depends(get_db)):
    stmt = select(Experiment)
    if project_id is not None:
        stmt = stmt.where(Experiment.project_id == project_id)
    if status_filter:
        if status_filter not in STATUSES:
            raise ValidationFailed(f"Unknown status '{status_filter}'.")
        stmt = stmt.where(Experiment.status == status_filter)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(stmt.order_by(Experiment.updated_at.desc()).limit(page.limit).offset(page.offset)).all()
    return Page(items=[out(e) for e in items], total=total, limit=page.limit, offset=page.offset)


@router.get("/{experiment_id}", response_model=ExperimentOut)
def get_experiment(exp: Experiment = Depends(experiment_dep)):
    return out(exp)


@router.patch("/{experiment_id}", response_model=ExperimentOut)
def update_experiment(body: ExperimentUpdate, exp: Experiment = Depends(experiment_dep), db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    new_status = data.pop("status", None)
    for k, v in data.items():
        if v is not None:
            setattr(exp, k, v)
    if new_status:
        change_status(db, exp, new_status)
    db.commit()
    db.refresh(exp)
    return out(exp)


@router.post("/{experiment_id}/results", response_model=ExperimentOut, status_code=status.HTTP_201_CREATED)
def add_result(body: ManualResult, exp: Experiment = Depends(experiment_dep), db: Session = Depends(get_db)):
    exp.results.append(ExperimentResult(metric_name=body.metric_name, baseline_value=body.baseline_value, new_value=body.new_value,
                                        higher_is_better=body.higher_is_better, source="manual", notes=body.notes))
    log_activity(db, "experiment", f"Recorded a result for experiment '{exp.title}'.", exp.project_id, f"/experiments?focus={exp.id}")
    db.commit()
    db.refresh(exp)
    return out(exp)


@router.post("/{experiment_id}/measure", response_model=ExperimentOut, status_code=status.HTTP_201_CREATED)
def measure(body: MeasureRequest, exp: Experiment = Depends(experiment_dep), db: Session = Depends(get_db)):
    cand = get_or_404(db, EvaluationRun, body.candidate_run_id, "Evaluation run")
    measure_from_runs(db, exp, cand)
    db.commit()
    db.refresh(exp)
    return out(exp)


@router.delete("/{experiment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_experiment(exp: Experiment = Depends(experiment_dep), db: Session = Depends(get_db)):
    log_activity(db, "experiment", f"Deleted experiment '{exp.title}'.", exp.project_id)
    db.delete(exp)
    db.commit()
