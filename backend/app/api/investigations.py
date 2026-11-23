from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import Pagination, get_or_404, investigation_dep
from app.core.errors import NotFoundError
from app.database.session import get_db
from app.investigator.service import investigation_payload, run_investigation
from app.models import EvaluationRun, Investigation
from app.schemas.common import Page
from app.services.cases import build_case

router = APIRouter(prefix="/investigations", tags=["investigations"])


class InvestigationRequest(BaseModel):
    run_id: int
    failure_group_ids: list[int] | None = Field(None, max_length=4)
    model: str | None = Field(None, max_length=100, pattern=r"^[A-Za-z0-9._:/-]+$")


@router.post("/run", status_code=status.HTTP_201_CREATED)
def start(body: InvestigationRequest, db: Session = Depends(get_db)) -> dict:
    run = get_or_404(db, EvaluationRun, body.run_id, "Evaluation run")
    return investigation_payload(run_investigation(db, run, body.failure_group_ids, body.model))


@router.get("", response_model=Page[dict])
def list_investigations(project_id: int | None = None, run_id: int | None = None, page: Pagination = Depends(), db: Session = Depends(get_db)):
    stmt = select(Investigation)
    if project_id is not None:
        stmt = stmt.where(Investigation.project_id == project_id)
    if run_id is not None:
        stmt = stmt.where(Investigation.run_id == run_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(stmt.order_by(Investigation.created_at.desc()).limit(page.limit).offset(page.offset)).all()
    return Page(items=[investigation_payload(i) for i in items], total=total, limit=page.limit, offset=page.offset)


@router.get("/{investigation_id}")
def get_investigation(inv: Investigation = Depends(investigation_dep)) -> dict:
    return investigation_payload(inv)


@router.get("/{investigation_id}/evidence")
def evidence(inv: Investigation = Depends(investigation_dep)) -> list[dict]:
    return [{"evidence_id": e.evidence_key, "kind": e.kind, "title": e.title, "record_index": e.record_index, "content": e.content}
            for e in inv.evidence]


@router.get("/{investigation_id}/evidence/{evidence_id}")
def evidence_item(evidence_id: str, inv: Investigation = Depends(investigation_dep)) -> dict:
    """One evidence item; for record-backed items, the full record with expected and actual output."""
    item = next((e for e in inv.evidence if e.evidence_key == evidence_id), None)
    if item is None:
        raise NotFoundError(f"{evidence_id} is not part of investigation {inv.id}.")
    out = {"evidence_id": item.evidence_key, "kind": item.kind, "title": item.title, "record_index": item.record_index, "content": item.content}
    if item.record_index is not None:
        out["record"] = build_case(inv.run.dataset, inv.run, item.record_index)
    return out


@router.delete("/{investigation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_investigation(inv: Investigation = Depends(investigation_dep), db: Session = Depends(get_db)):
    db.delete(inv)
    db.commit()
