from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from auth import require_active_team
import models
import schemas

router = APIRouter(prefix="/api/batches", tags=["batches"])


@router.post("/initialize")
def initialize_batches(
    n: int = Query(default=10, ge=2, le=50),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_active_team),
):
    """Split all team clips into n labeling batches (round-robin). One-time per team."""
    existing = (
        db.query(models.LabelingBatch)
        .filter(models.LabelingBatch.team_id == current_user.team_id)
        .count()
    )
    if existing > 0:
        raise HTTPException(400, f"Ya existen {existing} lotes para este equipo.")

    clips = (
        db.query(models.EventClip)
        .filter(models.EventClip.team_id == current_user.team_id)
        .order_by(models.EventClip.id)
        .all()
    )
    if not clips:
        raise HTTPException(404, "No hay clips para distribuir en lotes.")

    batch_count = min(n, len(clips))
    batches = []
    for i in range(batch_count):
        b = models.LabelingBatch(team_id=current_user.team_id, name=f"Lote {i + 1}")
        db.add(b)
        db.flush()
        batches.append(b)

    for i, clip in enumerate(clips):
        clip.batch_id = batches[i % batch_count].id

    db.commit()
    return {"created": batch_count, "clips_distributed": len(clips)}


@router.get("/", response_model=list[schemas.LabelingBatchOut])
def list_batches(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_active_team),
):
    batches = (
        db.query(models.LabelingBatch)
        .filter(models.LabelingBatch.team_id == current_user.team_id)
        .order_by(models.LabelingBatch.id)
        .all()
    )

    # Efficient batch stats: one group-by query per batch
    result = []
    for b in batches:
        rows = (
            db.query(models.EventClip.label_source, func.count(models.EventClip.id))
            .filter(models.EventClip.batch_id == b.id)
            .group_by(models.EventClip.label_source)
            .all()
        )
        counts = {src: cnt for src, cnt in rows}
        out = schemas.LabelingBatchOut.model_validate(b)
        out.total = sum(counts.values())
        out.manual = counts.get("manual", 0)
        out.pseudo = counts.get("pseudo", 0)
        out.pending = counts.get("pending", 0)
        result.append(out)
    return result


@router.patch("/{batch_id}/complete", response_model=schemas.LabelingBatchOut)
def complete_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_active_team),
):
    b = db.query(models.LabelingBatch).filter(
        models.LabelingBatch.id == batch_id,
        models.LabelingBatch.team_id == current_user.team_id,
    ).first()
    if not b:
        raise HTTPException(404, "Lote no encontrado.")
    b.status = "completed"
    b.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(b)
    # Attach stats
    rows = (
        db.query(models.EventClip.label_source, func.count(models.EventClip.id))
        .filter(models.EventClip.batch_id == b.id)
        .group_by(models.EventClip.label_source)
        .all()
    )
    counts = {src: cnt for src, cnt in rows}
    out = schemas.LabelingBatchOut.model_validate(b)
    out.total = sum(counts.values())
    out.manual = counts.get("manual", 0)
    out.pseudo = counts.get("pseudo", 0)
    out.pending = counts.get("pending", 0)
    return out


@router.post("/redistribute")
def redistribute_clips(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_active_team),
):
    """Assign all clips without a batch to existing batches (round-robin by load)."""
    batches = (
        db.query(models.LabelingBatch)
        .filter(models.LabelingBatch.team_id == current_user.team_id)
        .order_by(models.LabelingBatch.id)
        .all()
    )
    if not batches:
        raise HTTPException(400, "No hay lotes. Inicializa lotes primero.")

    unassigned = db.query(models.EventClip).filter(
        models.EventClip.team_id == current_user.team_id,
        models.EventClip.batch_id.is_(None),
    ).all()

    if not unassigned:
        return {"assigned": 0, "message": "No hay clips sin lote."}

    rows = (
        db.query(models.EventClip.batch_id, func.count(models.EventClip.id))
        .filter(models.EventClip.batch_id.in_([b.id for b in batches]))
        .group_by(models.EventClip.batch_id)
        .all()
    )
    counts = {b.id: 0 for b in batches}
    for bid, cnt in rows:
        counts[bid] = cnt

    sorted_batches = sorted(batches, key=lambda b: counts[b.id])
    for i, clip in enumerate(unassigned):
        batch = sorted_batches[i % len(sorted_batches)]
        clip.batch_id = batch.id
        counts[batch.id] += 1

    db.commit()
    return {"assigned": len(unassigned), "batches_used": len(batches)}


@router.get("/{batch_id}/clips", response_model=list[schemas.EventClipOut])
def get_batch_clips(
    batch_id: int,
    source: Optional[str] = Query(None, description="pending | pseudo | manual"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_active_team),
):
    b = db.query(models.LabelingBatch).filter(
        models.LabelingBatch.id == batch_id,
        models.LabelingBatch.team_id == current_user.team_id,
    ).first()
    if not b:
        raise HTTPException(404, "Lote no encontrado.")

    query = db.query(models.EventClip).filter(
        models.EventClip.batch_id == batch_id,
        models.EventClip.team_id == current_user.team_id,
    )
    if source in ("pending", "pseudo", "manual"):
        query = query.filter(models.EventClip.label_source == source)

    return query.order_by(models.EventClip.timestamp_seconds).all()
