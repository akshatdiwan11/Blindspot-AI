from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.demo.catalog import DEMOS, to_csv_bytes
from app.models import EvaluationRun, Project
from app.schemas.dataset import ColumnMapping
from app.services.activity import log_activity
from app.services.dataset_service import apply_mapping, create_dataset
from app.services.evaluation_service import run_evaluation


def load_demo(db: Session, key: str) -> tuple[Project, EvaluationRun]:
    spec = DEMOS.get(key)
    if spec is None:
        raise NotFoundError(f"Unknown demo '{key}'. Available: {', '.join(DEMOS)}.")
    records, _ = spec.generate()
    project = Project(name=spec.project_name, description=spec.description, model_category=spec.model_category,
                      evaluation_task=spec.task, is_demo=True, llm_investigation_enabled=False)
    db.add(project)
    db.flush()
    project_id = project.id
    try:
        log_activity(db, "project", f"Loaded synthetic demo '{spec.project_name}'.", project.id, f"/projects/{project.id}")
        ds = create_dataset(db, project, to_csv_bytes(records), spec.filename, spec.filename.rsplit(".", 1)[0], is_synthetic=True)
        apply_mapping(db, ds, ColumnMapping(**spec.mapping))
        run = run_evaluation(db, project, ds, {"task_type": spec.task, "label": "Baseline (synthetic)"})
    except Exception:
        # Never leave a half-built demo project behind.
        db.rollback()
        leftover = db.get(Project, project_id)
        if leftover is not None:
            db.delete(leftover)
            db.commit()
        raise
    return project, run
