from sqlalchemy.orm import Session

from app.models import ActivityEvent


def log_activity(db: Session, kind: str, message: str, project_id: int | None = None, link: str | None = None) -> None:
    db.add(ActivityEvent(kind=kind, message=message, project_id=project_id, link=link))
