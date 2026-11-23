from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import run_dep
from app.database.session import get_db
from app.models import EvaluationRun
from app.services.report_service import build_report, to_csv, to_markdown, to_pdf

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{run_id}")
def report(run: EvaluationRun = Depends(run_dep), db: Session = Depends(get_db),
           format: str = Query("json", pattern="^(json|markdown|md|csv|pdf)$"), investigation_id: int | None = None,
           download: bool = False):
    stem = f"blindspot_run{run.id}_{run.created_at:%Y%m%d-%H%M%S}"
    disp = (lambda ext: {"Content-Disposition": f'attachment; filename="{stem}.{ext}"'} if download else {})  # noqa: E731
    if format == "csv":
        return Response(to_csv(db, run), media_type="text/csv; charset=utf-8", headers=disp("csv"))
    r = build_report(db, run, investigation_id)
    if format in ("markdown", "md"):
        return Response(to_markdown(r), media_type="text/markdown; charset=utf-8", headers=disp("md"))
    if format == "pdf":
        return Response(to_pdf(r), media_type="application/pdf", headers={"Content-Disposition": f'{"attachment" if download else "inline"}; filename="{stem}.pdf"'})
    return Response(json.dumps(r, ensure_ascii=False, indent=2, default=str), media_type="application/json", headers=disp("json"))
