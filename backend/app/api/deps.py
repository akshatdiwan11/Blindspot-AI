from __future__ import annotations

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.database.session import get_db
from app.models import Dataset, EvaluationRun, Experiment, Investigation, Project


class Pagination:
    def __init__(self, limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)):
        self.limit = limit
        self.offset = offset


def get_or_404(db: Session, model, obj_id: int, label: str):
    obj = db.get(model, obj_id)
    if obj is None:
        raise NotFoundError(f"{label} {obj_id} was not found.")
    return obj


def project_dep(project_id: int, db: Session = Depends(get_db)) -> Project:
    return get_or_404(db, Project, project_id, "Project")


def dataset_dep(dataset_id: int, db: Session = Depends(get_db)) -> Dataset:
    return get_or_404(db, Dataset, dataset_id, "Dataset")


def run_dep(run_id: int, db: Session = Depends(get_db)) -> EvaluationRun:
    return get_or_404(db, EvaluationRun, run_id, "Evaluation run")


def investigation_dep(investigation_id: int, db: Session = Depends(get_db)) -> Investigation:
    return get_or_404(db, Investigation, investigation_id, "Investigation")


def experiment_dep(experiment_id: int, db: Session = Depends(get_db)) -> Experiment:
    return get_or_404(db, Experiment, experiment_id, "Experiment")
