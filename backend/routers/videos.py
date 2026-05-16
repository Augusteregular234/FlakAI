import os
import uuid
import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload
from database import get_db
from auth import require_active_team
from billing.subscription import PREMIUM_TIER, can_start_upload
import models, schemas
from ai_worker import process_video

router = APIRouter(prefix="/api/videos", tags=["videos"])

UPLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
CHUNK_DIR = os.path.join(UPLOADS_DIR, "chunks")

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(CHUNK_DIR, exist_ok=True)


@router.get("/", response_model=list[schemas.VideoOut])
def list_videos(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_active_team),
):
    videos = (
        db.query(models.VideoMatch)
        .options(joinedload(models.VideoMatch.events))
        .filter(models.VideoMatch.team_id == current_user.team_id)
        .order_by(models.VideoMatch.created_at.desc())
        .all()
    )
    result = []
    for v in videos:
        total = len(v.events)
        pending = sum(1 for e in v.events if e.review_status == models.ReviewStatus.pending)
        vo = schemas.VideoOut.model_validate(v)
        vo.event_count = total
        vo.pending_count = pending
        result.append(vo)
    return result


@router.post("/upload/init")
def init_upload(
    filename: str = Form(...),
    file_size: int = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_active_team),
):
    if not current_user.is_admin:
        team = (
            db.query(models.Team).filter(models.Team.id == current_user.team_id).first()
        )
        if not team:
            raise HTTPException(status_code=403, detail="Equipo no encontrado")
        allowed, reason = can_start_upload(team)
        if not allowed:
            raise HTTPException(status_code=403, detail=reason)

    upload_id = str(uuid.uuid4())
    safe_name = f"{upload_id}_{filename.replace(' ', '_')}"
    file_path = os.path.join(UPLOADS_DIR, safe_name)

    video = models.VideoMatch(
        team_id=current_user.team_id,
        user_id=current_user.id,
        filename=safe_name,
        original_name=filename,
        file_path=file_path,
        file_size=file_size,
        upload_id=upload_id,
        status=models.VideoStatus.uploading,
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    chunk_dir = os.path.join(CHUNK_DIR, upload_id)
    os.makedirs(chunk_dir, exist_ok=True)

    return {"upload_id": upload_id, "video_id": video.id}


@router.post("/upload/{upload_id}/chunk")
async def upload_chunk(
    upload_id: str,
    chunk_index: int = Form(...),
    chunk: UploadFile = File(...),
    current_user: models.User = Depends(require_active_team),
):
    chunk_dir = os.path.join(CHUNK_DIR, upload_id)
    if not os.path.exists(chunk_dir):
        raise HTTPException(status_code=404, detail="Upload session not found")

    chunk_path = os.path.join(chunk_dir, f"{chunk_index:06d}")
    async with aiofiles.open(chunk_path, "wb") as f:
        await f.write(await chunk.read())

    return {"chunk_index": chunk_index, "status": "received"}


@router.post("/upload/{upload_id}/complete")
async def complete_upload(
    upload_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_active_team),
):
    video = db.query(models.VideoMatch).filter(models.VideoMatch.upload_id == upload_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Upload not found")

    chunk_dir = os.path.join(CHUNK_DIR, upload_id)
    chunk_files = sorted(os.listdir(chunk_dir))

    async with aiofiles.open(video.file_path, "wb") as out_file:
        for chunk_file in chunk_files:
            chunk_path = os.path.join(chunk_dir, chunk_file)
            async with aiofiles.open(chunk_path, "rb") as f:
                await out_file.write(await f.read())

    import shutil
    shutil.rmtree(chunk_dir, ignore_errors=True)

    video.status = models.VideoStatus.queued

    team = (
        db.query(models.Team).filter(models.Team.id == video.team_id).first()
    )
    if team and team.subscription_tier != PREMIUM_TIER:
        team.trial_video_used = True

    db.commit()

    background_tasks.add_task(process_video, video.id)

    return {"video_id": video.id, "status": "queued"}


@router.delete("/{video_id}")
def delete_video(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_active_team),
):
    """
    Cancel and delete a video. Allowed for any status except 'processing'
    (processing videos are mid-FFmpeg — wait for completion or error first).
    Deletes the DB record and any associated clips.
    """
    import shutil

    video = db.query(models.VideoMatch).filter(
        models.VideoMatch.id == video_id,
        models.VideoMatch.team_id == current_user.team_id,
    ).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if video.status == models.VideoStatus.processing:
        raise HTTPException(
            status_code=409,
            detail="El vídeo se está procesando. Espera a que acabe o falle antes de eliminarlo.",
        )

    # Delete clip files
    clips = db.query(models.EventClip).filter(models.EventClip.video_id == video_id).all()
    for clip in clips:
        if clip.clip_path and os.path.exists(clip.clip_path):
            try:
                os.remove(clip.clip_path)
            except OSError:
                pass
        db.delete(clip)

    # Delete chunk dir if exists
    chunk_dir = os.path.join(CHUNK_DIR, video.upload_id)
    if os.path.exists(chunk_dir):
        shutil.rmtree(chunk_dir, ignore_errors=True)

    db.delete(video)
    db.commit()
    return {"deleted": video_id}


@router.get("/{video_id}", response_model=schemas.VideoOut)
def get_video(
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
    vo = schemas.VideoOut.model_validate(video)
    vo.event_count = len(video.events)
    vo.pending_count = sum(1 for e in video.events if e.review_status == models.ReviewStatus.pending)
    return vo
