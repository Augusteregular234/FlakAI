import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
import models
import schemas
from auth import get_current_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])

_VIDEO_EXT = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v"}


@router.delete("/videos/stuck")
def delete_stuck_videos(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    """Delete videos stuck in uploading/queued/error/processing with no clips."""
    stuck_statuses = [
        models.VideoStatus.uploading,
        models.VideoStatus.queued,
        models.VideoStatus.error,
        models.VideoStatus.processing,
    ]
    stuck = db.query(models.VideoMatch).filter(
        models.VideoMatch.status.in_(stuck_statuses)
    ).all()
    deleted = 0
    for v in stuck:
        clips = db.query(models.EventClip).filter(models.EventClip.video_id == v.id).count()
        if clips == 0:
            db.delete(v)
            deleted += 1
    db.commit()
    return {"deleted": deleted}


@router.post("/videos/trigger-queued")
async def trigger_queued_videos(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    """Trigger AI processing for all videos currently in queued status."""
    from ai_worker import process_video
    queued = db.query(models.VideoMatch).filter(
        models.VideoMatch.status == models.VideoStatus.queued
    ).all()
    for v in queued:
        asyncio.create_task(process_video(v.id))
    return {"triggered": len(queued), "ids": [v.id for v in queued]}


@router.post("/videos/ingest")
async def ingest_videos_from_paths(
    paths: List[str],
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin),
):
    """
    Queue local video files for processing without re-uploading.
    Skips files already in the DB (by original_name).
    """
    from ai_worker import process_video

    existing_names = {v.original_name for v in db.query(models.VideoMatch).all()}

    created_ids = []
    skipped = []
    for raw_path in paths:
        p = Path(raw_path)
        if not p.exists():
            skipped.append(f"not_found:{p.name}")
            continue
        if p.suffix.lower() not in _VIDEO_EXT:
            skipped.append(f"bad_ext:{p.name}")
            continue
        if p.name in existing_names:
            skipped.append(f"duplicate:{p.name}")
            continue

        video = models.VideoMatch(
            team_id=current_admin.team_id,
            user_id=current_admin.id,
            filename=p.name,
            original_name=p.name,
            file_path=str(p),
            file_size=p.stat().st_size,
            status=models.VideoStatus.queued,
            upload_id=str(uuid.uuid4()),
            created_at=datetime.utcnow(),
        )
        db.add(video)
        db.flush()
        created_ids.append(video.id)
        existing_names.add(p.name)

    db.commit()

    for vid_id in created_ids:
        asyncio.create_task(process_video(vid_id))

    return {"queued": len(created_ids), "skipped": len(skipped), "video_ids": created_ids}


@router.get("/teams/pending", response_model=list[schemas.TeamOut])
def list_pending_teams(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    q = db.query(models.Team).filter(
        models.Team.status == models.TeamStatus.pending_approval
    )
    return q.order_by(models.Team.id.desc()).all()


@router.post("/teams/{team_id}/approve", response_model=schemas.TeamOut)
def approve_team(
    team_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    if team.status != models.TeamStatus.pending_approval:
        raise HTTPException(status_code=400, detail="El equipo no está pendiente de aprobación")

    team.status = models.TeamStatus.active
    team.approved_at = datetime.utcnow()
    team.approved_by_user_id = admin.id
    db.commit()
    db.refresh(team)
    return team


@router.post("/teams/{team_id}/reject", response_model=schemas.TeamOut)
def reject_team(
    team_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    if team.status != models.TeamStatus.pending_approval:
        raise HTTPException(status_code=400, detail="El equipo no está pendiente de aprobación")

    team.status = models.TeamStatus.rejected
    team.approved_at = datetime.utcnow()
    team.approved_by_user_id = admin.id
    base = team.name.split(" [rechazado-", 1)[0]
    team.name = f"{base} [rechazado-{team.id}]"

    db.commit()
    db.refresh(team)
    return team
