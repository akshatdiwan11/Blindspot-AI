from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.database.session import SessionLocal
from app.models import Project
from app.models.base import utcnow

log = logging.getLogger(__name__)


def apply_retention_policy() -> int:
    """Delete projects older than RETENTION_DAYS (0 disables). Returns the number deleted."""
    days = get_settings().retention_days
    if days <= 0:
        return 0
    cutoff = utcnow() - timedelta(days=days)
    with SessionLocal() as db:
        old = db.scalars(select(Project).where(Project.created_at < cutoff, Project.is_demo.is_(False))).all()
        for p in old:
            db.delete(p)
        db.commit()
        if old:
            log.info("Retention policy removed %d project(s) older than %d days", len(old), days)
        return len(old)


def on_startup() -> None:
    settings = get_settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    try:
        apply_retention_policy()
    except Exception:  # the database may not be migrated yet; never block startup on housekeeping
        log.exception("Retention policy failed")
