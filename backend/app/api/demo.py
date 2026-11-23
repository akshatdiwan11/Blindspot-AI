from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.demo.catalog import DEMOS
from app.services.demo_service import load_demo

router = APIRouter(prefix="/demo", tags=["demo"])


@router.get("")
def list_demos() -> list[dict]:
    return [{"key": d.key, "name": d.project_name, "description": d.description, "task": d.task,
             "records": d.benchmark.get("records"), "planted_patterns": [p["id"] for p in d.benchmark.get("planted_patterns", [])]}
            for d in DEMOS.values()]


@router.post("/{key}", status_code=status.HTTP_201_CREATED)
def create_demo(key: str, db: Session = Depends(get_db)) -> dict:
    project, run = load_demo(db, key)
    return {"project_id": project.id, "run_id": run.id, "dataset_id": run.dataset_id, "synthetic": True}
