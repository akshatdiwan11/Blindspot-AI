from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import Pagination, get_or_404, project_dep, run_dep
from app.core.errors import NotFoundError
from app.database.session import get_db
from app.models import Cluster, Dataset, EvaluationRun, FailureGroup, Project
from app.schemas.common import Page
from app.schemas.evaluation import (CaseRecord, ClusterDetail, ClusterOut, EvaluationRunRequest, FailureGroupDetail, FailureGroupOut,
                                    RunComparison, RunDetail, RunSummary)
from app.services.activity import log_activity
from app.services.cases import build_case, case_lookup
from app.services.comparison import compare_runs
from app.services.evaluation_service import run_evaluation

router = APIRouter(tags=["evaluations"])


def run_detail(run: EvaluationRun) -> RunDetail:
    d = RunDetail.model_validate(run)
    d.dataset_name = run.dataset.name if run.dataset else ""
    d.failure_group_count = len(run.failure_groups)
    d.cluster_count = len(run.clusters)
    return d


@router.post("/evaluations/run", response_model=RunDetail, status_code=status.HTTP_201_CREATED)
def start_evaluation(body: EvaluationRunRequest, db: Session = Depends(get_db)):
    ds = get_or_404(db, Dataset, body.dataset_id, "Dataset")
    project = db.get(Project, ds.project_id)
    run = run_evaluation(db, project, ds, body.config)
    return run_detail(run)


@router.get("/evaluations", response_model=Page[RunSummary])
def list_all_runs(page: Pagination = Depends(), db: Session = Depends(get_db)):
    total = db.scalar(select(func.count(EvaluationRun.id))) or 0
    items = db.scalars(select(EvaluationRun).order_by(EvaluationRun.created_at.desc()).limit(page.limit).offset(page.offset)).all()
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


@router.get("/evaluations/compare", response_model=RunComparison)
def compare(run_a: int = Query(...), run_b: int = Query(...), db: Session = Depends(get_db)):
    a = get_or_404(db, EvaluationRun, run_a, "Evaluation run")
    b = get_or_404(db, EvaluationRun, run_b, "Evaluation run")
    result = compare_runs(a, b)
    return RunComparison(run_a=RunSummary.model_validate(a), run_b=RunSummary.model_validate(b), **result)


@router.get("/evaluations/{run_id}", response_model=RunDetail)
def get_run(run: EvaluationRun = Depends(run_dep)):
    return run_detail(run)


@router.delete("/evaluations/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_run(run: EvaluationRun = Depends(run_dep), db: Session = Depends(get_db)):
    log_activity(db, "evaluation", f"Deleted evaluation run #{run.id}.", run.project_id)
    db.delete(run)
    db.commit()


@router.get("/projects/{project_id}/evaluations", response_model=Page[RunSummary])
def project_runs(project: Project = Depends(project_dep), page: Pagination = Depends(), db: Session = Depends(get_db)):
    stmt = select(EvaluationRun).where(EvaluationRun.project_id == project.id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(stmt.order_by(EvaluationRun.created_at.desc()).limit(page.limit).offset(page.offset)).all()
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


@router.get("/evaluations/{run_id}/cases", response_model=Page[CaseRecord])
def run_cases(
    run: EvaluationRun = Depends(run_dep), page: Pagination = Depends(),
    outcome: str | None = Query(None, pattern="^(failed|passed)$"),
    error_type: str | None = Query(None, max_length=60),
    q: str | None = Query(None, max_length=200),
):
    lookup = case_lookup(run)
    cases = run.case_results
    if outcome:
        cases = [c for c in cases if c["correct"] == (outcome == "passed")]
    if error_type:
        cases = [c for c in cases if c["error_type"] == error_type]
    built = [build_case(run.dataset, run, c["index"], lookup) for c in cases]
    built = [b for b in built if b]
    if q:
        ql = q.lower()
        built = [b for b in built if ql in " ".join(str(v) for v in (b["case_id"], b["input"], b["expected"], b["actual"], *b["metadata"].values())).lower()]
    return Page(items=built[page.offset: page.offset + page.limit], total=len(built), limit=page.limit, offset=page.offset)


@router.get("/evaluations/{run_id}/cases/{index}", response_model=CaseRecord)
def run_case(index: int, run: EvaluationRun = Depends(run_dep)):
    c = build_case(run.dataset, run, index)
    if not c:
        raise NotFoundError(f"Record {index} was not evaluated in run {run.id}.")
    return c


@router.get("/evaluations/{run_id}/failure-groups", response_model=Page[FailureGroupOut])
def failure_groups(run: EvaluationRun = Depends(run_dep), page: Pagination = Depends(),
                   reliability: str | None = Query(None, pattern="^(reliable|tentative)$")):
    groups = [g for g in run.failure_groups if not reliability or g.reliability == reliability]
    return Page(items=groups[page.offset: page.offset + page.limit], total=len(groups), limit=page.limit, offset=page.offset)


@router.get("/evaluations/{run_id}/failure-groups/{group_id}", response_model=FailureGroupDetail)
def failure_group_detail(group_id: int, run: EvaluationRun = Depends(run_dep), db: Session = Depends(get_db),
                         limit: int = Query(25, ge=1, le=300)):
    g = db.get(FailureGroup, group_id)
    if not g or g.run_id != run.id:
        raise NotFoundError(f"Failure group {group_id} was not found in run {run.id}.")
    lookup = case_lookup(run)
    fails = sorted([e for e in g.examples if e.is_failure], key=lambda e: (not e.representative, e.record_index))
    oks = [e for e in g.examples if not e.is_failure]
    examples = [c for c in (build_case(run.dataset, run, e.record_index, lookup, e.representative) for e in fails[:limit]) if c]
    successes = [c for c in (build_case(run.dataset, run, e.record_index, lookup) for e in oks[: min(limit, 10)]) if c]
    return FailureGroupDetail.model_validate({**FailureGroupOut.model_validate(g).model_dump(), "examples": examples, "successes": successes})


@router.get("/evaluations/{run_id}/clusters", response_model=list[ClusterOut])
def clusters(run: EvaluationRun = Depends(run_dep)):
    return run.clusters


@router.get("/evaluations/{run_id}/clusters/{cluster_id}", response_model=ClusterDetail)
def cluster_detail(cluster_id: int, run: EvaluationRun = Depends(run_dep), db: Session = Depends(get_db), limit: int = Query(20, ge=1, le=200)):
    c = db.get(Cluster, cluster_id)
    if not c or c.run_id != run.id:
        raise NotFoundError(f"Cluster {cluster_id} was not found in run {run.id}.")
    lookup = case_lookup(run)
    reps = set(c.representative_indices)
    order = c.representative_indices + [i for i in c.member_indices if i not in reps]
    examples = [x for x in (build_case(run.dataset, run, i, lookup, i in reps) for i in order[:limit]) if x]
    return ClusterDetail.model_validate({**ClusterOut.model_validate(c).model_dump(), "examples": examples})
