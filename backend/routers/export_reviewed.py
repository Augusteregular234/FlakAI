"""Exportación de clips ya revisados (etiquetas humanas) para entrenamiento offline."""
from __future__ import annotations

import csv
import io
import json
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from auth import get_current_admin, require_active_team
from database import get_db
import models
from export_records import (
    EXPORT_FIELDNAMES,
    fetch_reviewed_clips,
    to_training_record,
)

router_team = APIRouter(prefix="/api/export", tags=["export"])
router_admin = APIRouter(prefix="/api/admin/export", tags=["export-admin"])


def _media_filename(scope: str, fmt: str) -> str:
    ext = "csv" if fmt == "csv" else "jsonl"
    return f"flakai_labels_{scope}.{ext}"


def _build_response(
    records: list[dict],
    fmt: Literal["jsonl", "csv"],
    scope: str,
) -> StreamingResponse:
    filename = _media_filename(scope, fmt)

    if fmt == "jsonl":

        def iter_jsonl():
            for r in records:
                yield json.dumps(r, ensure_ascii=False) + "\n"

        return StreamingResponse(
            iter_jsonl(),
            media_type="application/x-ndjson",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=EXPORT_FIELDNAMES, extrasaction="ignore")
    w.writeheader()
    for r in records:
        w.writerow(r)
    body = buf.getvalue().encode("utf-8")

    def iter_csv_one_shot():
        yield body

    return StreamingResponse(
        iter_csv_one_shot(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router_team.get("/reviewed")
def export_team_reviewed(
    export_format: Literal["jsonl", "csv"] = Query(
        "jsonl", alias="format", description="jsonl o csv"
    ),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_active_team),
):
    rows = fetch_reviewed_clips(db, team_id=current_user.team_id)
    records = [to_training_record(c, v, t) for c, v, t in rows]
    return _build_response(records, export_format, scope=f"team_{current_user.team_id}")


@router_admin.get("/reviewed")
def export_all_reviewed(
    export_format: Literal["jsonl", "csv"] = Query(
        "jsonl", alias="format", description="jsonl o csv"
    ),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    rows = fetch_reviewed_clips(db, team_id=None)
    records = [to_training_record(c, v, t) for c, v, t in rows]
    return _build_response(records, export_format, scope="all_teams")
