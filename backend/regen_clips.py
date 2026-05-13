"""Regenera todos los clips existentes con la ventana configurada en config.py."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from database import SessionLocal
import models
from clip_generation import generate_clip, resolve_ffmpeg_path
from config import get_settings
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("regen")

s = get_settings()
log.info("Ventana configurada: %.1fs (%.1fs antes + %.1fs despues del evento)",
         s.clip_window_seconds, s.clip_window_seconds/2, s.clip_window_seconds/2)

ffmpeg = resolve_ffmpeg_path()
if not ffmpeg:
    log.error("ffmpeg no encontrado")
    sys.exit(1)

db = SessionLocal()
clips = db.query(models.EventClip).join(models.VideoMatch).all()
total = len(clips)
ok = fail = skip = 0

for i, clip in enumerate(clips, 1):
    video = db.query(models.VideoMatch).filter(models.VideoMatch.id == clip.video_id).first()
    if not video or not os.path.exists(video.file_path):
        log.warning("[%d/%d] Video no encontrado para clip_id=%d", i, total, clip.id)
        skip += 1
        continue

    clips_dir = os.path.dirname(clip.clip_path)
    result = generate_clip(clips_dir, video.file_path, clip.timestamp_seconds, os.path.basename(clip.clip_path))
    if result and os.path.exists(result):
        size_kb = os.path.getsize(result) // 1024
        log.info("[%d/%d] OK  clip_id=%-4d  %s @ %.1fs  %dKB",
                 i, total, clip.id, clip.event_type.value, clip.timestamp_seconds, size_kb)
        ok += 1
    else:
        log.warning("[%d/%d] FAIL clip_id=%d", i, total, clip.id)
        fail += 1

db.close()
log.info("Completado: %d OK  %d fallidos  %d saltados de %d total", ok, fail, skip, total)
