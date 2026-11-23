from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import Pagination, project_dep
from app.database.session import get_db
from app.models import ActivityEvent, Dataset, EvaluationRun, FailureGroup, Project
from app.schemas.common import Page
from app.schemas.project import DEFAULT_TASK, ProjectCreate, ProjectOut, ProjectUpdate
from app.services.activity import log_activity
from app.services.dataset_service import delete_dataset_files

router = APIRouter(prefix="/projects", tags=["projects"])


def project_out(db: Session, p: Project) -> ProjectOut:
    latest = db.scalars(select(EvaluationRun).where(EvaluationRun.project_id == p.id, EvaluationRun.status == "completed").order_by(EvaluationRun.created_at.desc()).limit(1)).first()
    out = ProjectOut.model_validate(p)
    out.dataset_count = db.scalar(select(func.count(Dataset.id)).where(Dataset.project_id == p.id)) or 0
    out.run_count = db.scalar(select(func.count(EvaluationRun.id)).where(EvaluationRun.project_id == p.id)) or 0
    if latest:
        out.latest_run_id = latest.id
        out.latest_error_rate = latest.error_rate
        out.latest_headline_value = latest.headline_value
        out.failure_group_count = db.scalar(select(func.count(FailureGroup.id)).where(FailureGroup.run_id == latest.id)) or 0
    return out


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectCreate, db: Session = Depends(get_db)):
    p = Project(name=body.name, description=body.description, model_category=body.model_category,
                evaluation_task=body.evaluation_task or DEFAULT_TASK[body.model_category],
                llm_investigation_enabled=body.llm_investigation_enabled)
    db.add(p)
    db.flush()
    log_activity(db, "project", f"Created project '{p.name}'.", p.id, f"/projects/{p.id}")
    db.commit()
    return project_out(db, p)


@router.get("", response_model=Page[ProjectOut])
def list_projects(page: Pagination = Depends(), q: str | None = Query(None, max_length=100), db: Session = Depends(get_db)):
    stmt = select(Project)
    if q:
        stmt = stmt.where(Project.name.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(stmt.order_by(Project.updated_at.desc()).limit(page.limit).offset(page.offset)).all()
    return Page(items=[project_out(db, p) for p in items], total=total, limit=page.limit, offset=page.offset)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project: Project = Depends(project_dep), db: Session = Depends(get_db)):
    return project_out(db, project)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(body: ProjectUpdate, project: Project = Depends(project_dep), db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        project.name = data["name"].strip()
    if "description" in data and data["description"] is not None:
        project.description = data["description"]
    if "llm_investigation_enabled" in data and data["llm_investigation_enabled"] is not None:
        project.llm_investigation_enabled = data["llm_investigation_enabled"]
        log_activity(db, "settings", f"LLM investigation {'enabled' if project.llm_investigation_enabled else 'disabled'} for '{project.name}'.", project.id)
    db.commit()
    return project_out(db, project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project: Project = Depends(project_dep), db: Session = Depends(get_db)):
    for ds in project.datasets:
        delete_dataset_files(ds)
    name = project.name
    db.delete(project)
    db.add(ActivityEvent(kind="project", message=f"Deleted project '{name}' and all of its data."))
    db.commit()
