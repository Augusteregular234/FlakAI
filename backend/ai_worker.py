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

# Prevent CPU/RAM exhaustion: at most 2 videos processed concurrently.
# Each video runs up to 5 FFmpeg clip-extraction jobs sequentially inside
# its slot, so this caps active FFmpeg processes at 2 at any given time.
_PROCESSING_SEMAPHORE = asyncio.Semaphore(2)


def _auto_assign_batches(video_id: int, team_id: int) -> None:
    """Round-robin distribute new clips across existing team batches."""
    db: Session = SessionLocal()
    try:
        from sqlalchemy import func
        batches = db.query(models.LabelingBatch).filter(
            models.LabelingBatch.team_id == team_id
        ).order_by(models.LabelingBatch.id).all()
        if not batches:
            return

        unassigned = db.query(models.EventClip).filter(
            models.EventClip.video_id == video_id,
            models.EventClip.batch_id.is_(None),
        ).all()
        if not unassigned:
            return

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
        logger.info("Auto-assigned %d clips from video %d to %d batches", len(unassigned), video_id, len(batches))
    except Exception as e:
        logger.warning("Auto-assign batches failed for video %d: %s", video_id, e)
    finally:
        db.close()


async def process_video(video_id: int) -> None:
    # Marcar como en cola antes de esperar el semáforo
    db_q: Session = SessionLocal()
    try:
        v = db_q.query(models.VideoMatch).filter(models.VideoMatch.id == video_id).first()
        if v:
            v.status = models.VideoStatus.queued
            db_q.commit()
    finally:
        db_q.close()

    async with _PROCESSING_SEMAPHORE:
        await _do_process(video_id)


async def _do_process(video_id: int) -> None:
    await asyncio.sleep(0)  # yield before acquiring DB

    db: Session = SessionLocal()
    video: models.VideoMatch | None = None

    try:
        video = db.query(models.VideoMatch).filter(models.VideoMatch.id == video_id).first()
        if not video:
            logger.warning("process_video: video_id=%s no encontrado en DB", video_id)
            return

        logger.info(
            "process_video START video_id=%s file=%s size=%.1fMB",
            video_id, video.original_name, (video.file_size or 0) / 1_048_576,
        )

        video.status = models.VideoStatus.processing
        video.processing_started_at = datetime.utcnow()
        video.processing_events_done = 0
        video.processing_events_total = 0
        db.commit()

        settings = get_settings()

        duration = await asyncio.to_thread(probe_duration_seconds, video.file_path)
        if duration is not None:
            video.duration_seconds = duration
            db.commit()
            logger.info("process_video video_id=%s duración=%.1fs (%.1fmin)", video_id, duration, duration / 60)
        else:
            logger.warning("process_video video_id=%s no se pudo determinar duración — usando 5400s por defecto", video_id)

        await asyncio.sleep(0)

        detector = get_detector()
        logger.info("process_video video_id=%s detector=%s", video_id, detector.model_version)
        raw_events = detector.detect(video.file_path, duration)
        logger.info("process_video video_id=%s eventos_detectados=%d", video_id, len(raw_events))

        video.processing_events_total = len(raw_events)
        db.commit()

        clips_ok = 0
        clips_fail = 0

        for i, event_data in enumerate(raw_events):
            min_s = int(event_data.timestamp_seconds // 60)
            sec_s = int(event_data.timestamp_seconds % 60)
            logger.debug(
                "  evento[%d/%d] tipo=%-10s tiempo=%d'%02d\" confianza=%.1f%%",
                i + 1, len(raw_events),
                event_data.event_type.value,
                min_s, sec_s,
                event_data.confidence,
            )

            clip_filename = (
                f"clip_{video_id}_{int(event_data.timestamp_seconds)}_"
                f"{event_data.event_type.value}.mp4"
            )
            clip_path = await asyncio.to_thread(
                generate_clip,
                CLIPS_DIR,
                video.file_path,
                event_data.timestamp_seconds,
                clip_filename,
            )

            if clip_path and os.path.exists(clip_path):
                clips_ok += 1
            else:
                clips_fail += 1
                logger.warning("process_video: clip no generado para evento[%d] %s@%.1fs", i, event_data.event_type.value, event_data.timestamp_seconds)

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
            video.processing_events_done = i + 1
            db.commit()  # commit each clip immediately so it appears in the UI

        video.status = models.VideoStatus.completed
        video.processed_at = datetime.utcnow()
        db.commit()
        logger.info(
            "process_video DONE video_id=%s events=%d clips_ok=%d clips_fail=%d model=%s",
            video_id, len(raw_events), clips_ok, clips_fail, detector.model_version,
        )

        # Auto-assign new clips to existing batches
        _auto_assign_batches(video_id, video.team_id)

    except Exception:
        logger.exception("process_video FAILED video_id=%s", video_id)
        db.rollback()
        video_err = db.query(models.VideoMatch).filter(models.VideoMatch.id == video_id).first()
        if video_err:
            video_err.status = models.VideoStatus.error
            db.commit()
    finally:
        db.close()
