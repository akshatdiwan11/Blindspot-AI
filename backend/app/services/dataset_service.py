from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import PayloadTooLarge, ValidationFailed
from app.models import Dataset, Project
from app.schemas.dataset import ColumnMapping
from app.services.activity import log_activity
from app.services.profiling import build_profile, validate_mapping_against
from app.utils.parsing import parse_upload

log = logging.getLogger(__name__)
_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(name: str) -> str:
    base = Path(name or "upload").name  # strip any path components
    base = _SAFE.sub("_", base).strip("._") or "upload"
    return base[:120]


def create_dataset(db: Session, project: Project, raw: bytes, filename: str, name: str | None = None, *, is_synthetic: bool = False) -> Dataset:
    settings = get_settings()
    if len(raw) > settings.max_upload_bytes:
        raise PayloadTooLarge(f"The file is {len(raw) / 1e6:.1f} MB. The upload limit is {settings.max_upload_mb:g} MB.")
    fmt, parsed = parse_upload(raw, filename, max_rows=settings.max_rows)
    profile = build_profile(parsed.columns, parsed.rows, parsed.invalid_rows, parsed.warnings)
    ds_name = (name or Path(filename).stem or "dataset").strip()[:200]
    version = (db.scalar(select(func.max(Dataset.version)).where(Dataset.project_id == project.id, Dataset.name == ds_name)) or 0) + 1
    digest = hashlib.sha256(raw).hexdigest()

    stored_path = None
    try:  # keep the original file for provenance; the parsed rows live in the database
        folder = settings.storage_dir / f"project_{project.id}"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{digest[:12]}_v{version}_{safe_filename(filename)}"
        path.write_bytes(raw)
        stored_path = str(path)
    except OSError:
        log.warning("Could not store the original upload on disk; continuing with database copy only")

    ds = Dataset(
        project_id=project.id, name=ds_name, version=version, file_format=fmt, original_filename=safe_filename(filename),
        stored_path=stored_path, size_bytes=len(raw), sha256=digest, row_count=len(parsed.rows),
        columns=[{k: c[k] for k in ("name", "dtype", "missing", "unique")} for c in profile["columns"]],
        profile=profile, status="needs_mapping", is_synthetic=is_synthetic, records=parsed.rows,
    )
    db.add(ds)
    db.flush()
    log_activity(db, "dataset", f"Uploaded dataset '{ds_name}' v{version} ({len(parsed.rows):,} records).", project.id, f"/datasets/{ds.id}")
    db.commit()
    db.refresh(ds)
    return ds


def apply_mapping(db: Session, ds: Dataset, mapping: ColumnMapping) -> dict:
    names = {c["name"] for c in ds.columns}
    referenced = [mapping.expected_column, mapping.actual_column, mapping.input_column, mapping.case_id_column, *mapping.metadata_columns]
    unknown = [c for c in referenced if c and c not in names]
    if unknown:
        raise ValidationFailed(f"Unknown column(s): {', '.join(unknown)}.", details={"available_columns": sorted(names)})
    m = mapping.model_dump()
    check = validate_mapping_against(ds.records, m)
    if check["valid_records"] == 0:
        raise ValidationFailed("No record has an expected output in the selected column. Choose a different expected-output column.")
    m["metadata_columns"] = [c for c in m["metadata_columns"] if c not in check["leaky_metadata_columns"]]
    ds.column_mapping = m
    ds.status = "ready"
    ds.profile = {**ds.profile, "mapping_check": check}
    db.commit()
    db.refresh(ds)
    return check


def delete_dataset_files(ds: Dataset) -> None:
    if ds.stored_path:
        try:
            Path(ds.stored_path).unlink(missing_ok=True)
        except OSError:
            log.warning("Could not delete stored file %s", ds.stored_path)
