"""Extracción de clips con FFmpeg (configurable, PATH o FFMPEG_PATH)."""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

from config import get_settings

logger = logging.getLogger(__name__)


def resolve_ffmpeg_path() -> str | None:
    s = get_settings()
    if s.ffmpeg_path:
        p = Path(s.ffmpeg_path)
        if p.exists():
            return str(p)
    w = shutil.which("ffmpeg")
    if w:
        return w
    return None


def generate_clip(
    clips_dir: str,
    video_path: str,
    event_timestamp: float,
    clip_filename: str,
) -> str | None:
    os.makedirs(clips_dir, exist_ok=True)
    clip_path = os.path.join(clips_dir, clip_filename)
    s = get_settings()
    window = float(s.clip_window_seconds)
    start = max(0.0, event_timestamp)

    ffmpeg = resolve_ffmpeg_path()
    if not ffmpeg:
        logger.warning("ffmpeg no encontrado; generando clip dummy para %s", clip_filename)
        _create_dummy_clip(ffmpeg, clip_path)
        return clip_path

    if not os.path.exists(video_path):
        logger.warning("vídeo origen no existe: %s", video_path)
        _create_dummy_clip(ffmpeg, clip_path)
        return clip_path

    # Stream-copy: no re-encoding — identical quality, ~30x faster.
    # -ss before -i = fast keyframe seek; clip may start up to ~2s before event.
    cmd = [
        ffmpeg,
        "-y",
        "-ss", str(start),
        "-i", video_path,
        "-t", str(window),
        "-c", "copy",
        "-movflags", "+faststart",
        clip_path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode == 0 and os.path.exists(clip_path):
            size_kb = os.path.getsize(clip_path) // 1024
            logger.info(
                "generate_clip OK: %s (start=%.1fs, window=%.1fs, size=%dKB)",
                clip_filename, start, window, size_kb,
            )
            return clip_path
        err = result.stderr[-500:].decode(errors="replace") if result.stderr else ""
        logger.warning("ffmpeg falló (rc=%d) para %s: %s", result.returncode, clip_filename, err)
    except subprocess.TimeoutExpired:
        logger.warning("generate_clip: timeout 120s para %s", clip_filename)
    except Exception as e:
        logger.exception("generate_clip error para %s: %s", clip_filename, e)

    logger.warning("generate_clip: usando clip dummy para %s", clip_filename)
    _create_dummy_clip(ffmpeg, clip_path)
    return clip_path


def _create_dummy_clip(ffmpeg: str | None, clip_path: str) -> None:
    if not ffmpeg:
        with open(clip_path, "wb") as f:
            f.write(b"\x00" * 1024)
        return

    cmd = [
        ffmpeg,
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=1280x720:r=25:d=5",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=r=44100:cl=stereo",
        "-t",
        "5",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        clip_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=60)
    except Exception:
        with open(clip_path, "wb") as f:
            f.write(b"\x00" * 1024)
