import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from database import get_db
from auth import require_active_team, get_user_any_token
import models, schemas

router = APIRouter(prefix="/api/clips", tags=["clips"])


@router.get("/pending", response_model=list[schemas.EventClipOut])
def get_pending_clips(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_active_team),
):
    clips = (
        db.query(models.EventClip)
        .filter(
            models.EventClip.team_id == current_user.team_id,
            models.EventClip.review_status == models.ReviewStatus.pending,
        )
        .order_by(models.EventClip.created_at.desc())
        .all()
    )
    return clips


@router.get("/video/{video_id}", response_model=list[schemas.EventClipOut])
def get_clips_for_video(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_active_team),
):
    video = db.query(models.VideoMatch).filter(
        models.VideoMatch.id == video_id,
        models.VideoMatch.team_id == current_user.team_id,
    ).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    clips = (
        db.query(models.EventClip)
        .filter(models.EventClip.video_id == video_id)
        .order_by(models.EventClip.timestamp_seconds)
        .all()
    )
    return clips


@router.patch("/{clip_id}/review", response_model=schemas.EventClipOut)
def review_clip(
    clip_id: int,
    data: schemas.ReviewUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_active_team),
):
    clip = db.query(models.EventClip).filter(
        models.EventClip.id == clip_id,
        models.EventClip.team_id == current_user.team_id,
    ).first()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    clip.review_status = data.status
    if data.event_type is not None:
        clip.event_type = data.event_type
    db.commit()
    db.refresh(clip)
    return clip


@router.get("/{clip_id}/stream")
def stream_clip(
    clip_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_user_any_token),
):
    """Soporta auth via header Y via ?token= para que <video src> funcione en el navegador."""
    clip = db.query(models.EventClip).filter(
        models.EventClip.id == clip_id,
        models.EventClip.team_id == current_user.team_id,
    ).first()
    if not clip or not clip.clip_path:
        raise HTTPException(status_code=404, detail="Clip not found")
    if not os.path.exists(clip.clip_path):
        raise HTTPException(status_code=404, detail=f"Clip file missing on disk: {clip.clip_filename}")

    return FileResponse(
        clip.clip_path,
        media_type="video/mp4",
        headers={"Accept-Ranges": "bytes"},
    )
