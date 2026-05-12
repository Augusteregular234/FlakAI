import asyncio
import json
import logging
import os
from datetime import datetime

from sqlalchemy.orm import Session

import models
from clip_generation import generate_clip
from config import get_settings
from database import SessionLocal
from detection import get_detector
from video_probe import probe_duration_seconds

logger = logging.getLogger(__name__)

CLIPS_DIR = os.path.join(os.path.dirname(__file__), "clips")


async def process_video(video_id: int) -> None:
    await asyncio.sleep(1)

    db: Session = SessionLocal()
    video: models.VideoMatch | None = None

    try:
        video = db.query(models.VideoMatch).filter(models.VideoMatch.id == video_id).first()
        if not video:
            return

        video.status = models.VideoStatus.processing
        db.commit()

        settings = get_settings()
        duration = probe_duration_seconds(video.file_path)
        if duration is not None:
            video.duration_seconds = duration
            db.commit()

        await asyncio.sleep(2)

        detector = get_detector()
        raw_events = detector.detect(video.file_path, duration)

        for event_data in raw_events:
            clip_filename = (
                f"clip_{video_id}_{int(event_data.timestamp_seconds)}_"
                f"{event_data.event_type.value}.mp4"
            )
            clip_path = generate_clip(
                CLIPS_DIR,
                video.file_path,
                event_data.timestamp_seconds,
                clip_filename,
            )

            meta = json.dumps(event_data.extra or {}, ensure_ascii=False)
            review_status = (
                models.ReviewStatus.approved
                if event_data.confidence >= settings.auto_approve_confidence
                else models.ReviewStatus.pending
            )

            clip = models.EventClip(
                video_id=video.id,
                team_id=video.team_id,
                event_type=event_data.event_type,
                timestamp_seconds=event_data.timestamp_seconds,
                confidence=event_data.confidence,
                clip_path=clip_path,
                clip_filename=clip_filename,
                review_status=review_status,
                model_version=detector.model_version,
                detector_metadata=meta,
            )
            db.add(clip)

        video.status = models.VideoStatus.completed
        video.processed_at = datetime.utcnow()
        db.commit()
        logger.info(
            "process_video ok video_id=%s events=%s model=%s",
            video_id,
            len(raw_events),
            detector.model_version,
        )

    except Exception:
        logger.exception("process_video failed video_id=%s", video_id)
        db.rollback()
        video_err = db.query(models.VideoMatch).filter(models.VideoMatch.id == video_id).first()
        if video_err:
            video_err.status = models.VideoStatus.error
            db.commit()
    finally:
        db.close()
