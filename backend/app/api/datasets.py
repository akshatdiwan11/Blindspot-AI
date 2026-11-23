from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import Pagination, dataset_dep, get_or_404
from app.core.config import get_settings
from app.core.errors import PayloadTooLarge
from app.database.session import get_db
from app.models import Dataset, Project
from app.schemas.common import Page
from app.schemas.dataset import ColumnMapping, DatasetDetail, DatasetOut, DatasetPreview
from app.services.activity import log_activity
from app.services.dataset_service import apply_mapping, create_dataset, delete_dataset_files

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.post("/upload", response_model=DatasetDetail, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    project_id: int = Form(...),
    file: UploadFile = File(...),
    name: str | None = Form(None, max_length=200),
    db: Session = Depends(get_db),
):
    project = get_or_404(db, Project, project_id, "Project")
    limit = get_settings().max_upload_bytes
    raw = await file.read(limit + 1)
    if len(raw) > limit:
        raise PayloadTooLarge(f"The file is larger than the {get_settings().max_upload_mb:g} MB upload limit.")
    return create_dataset(db, project, raw, file.filename or "upload.csv", name)


@router.get("", response_model=Page[DatasetOut])
def list_datasets(project_id: int | None = None, q: str | None = Query(None, max_length=100), page: Pagination = Depends(), db: Session = Depends(get_db)):
    stmt = select(Dataset)
    if project_id is not None:
        stmt = stmt.where(Dataset.project_id == project_id)
    if q:
        stmt = stmt.where(Dataset.name.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(stmt.order_by(Dataset.created_at.desc()).limit(page.limit).offset(page.offset)).all()
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


@router.get("/{dataset_id}", response_model=DatasetDetail)
def get_dataset(ds: Dataset = Depends(dataset_dep)):
    return ds


@router.get("/{dataset_id}/preview", response_model=DatasetPreview)
def preview_dataset(
    ds: Dataset = Depends(dataset_dep),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: str | None = Query(None, max_length=200, description="Case-insensitive text filter across all columns"),
    column: str | None = Query(None, max_length=200),
    value: str | None = Query(None, max_length=500),
):
    rows = [{"_row": i + 1, **r} for i, r in enumerate(ds.records)]
    if column and value is not None:
        rows = [r for r in rows if str(r.get(column)) == value]
    if q:
        ql = q.lower()
        rows = [r for r in rows if any(ql in str(v).lower() for v in r.values() if v is not None)]
    return DatasetPreview(dataset=DatasetOut.model_validate(ds), profile=ds.profile, sample_rows=rows[offset: offset + limit],
                          total=len(rows), limit=limit, offset=offset, mapping_check=ds.profile.get("mapping_check"))


@router.put("/{dataset_id}/mapping", response_model=DatasetPreview)
def set_mapping(body: ColumnMapping, ds: Dataset = Depends(dataset_dep), db: Session = Depends(get_db)):
    check = apply_mapping(db, ds, body)
    rows = [{"_row": i + 1, **r} for i, r in enumerate(ds.records[:20])]
    return DatasetPreview(dataset=DatasetOut.model_validate(ds), profile=ds.profile, sample_rows=rows, total=ds.row_count, limit=20, offset=0, mapping_check=check)


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset(ds: Dataset = Depends(dataset_dep), db: Session = Depends(get_db)):
    delete_dataset_files(ds)
    log_activity(db, "dataset", f"Deleted dataset '{ds.name}' v{ds.version} and its evaluation runs.", ds.project_id)
    db.delete(ds)
    db.commit()
