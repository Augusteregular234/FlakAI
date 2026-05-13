"""Duración y metadatos de vídeo vía ffprobe (sin cargar el archivo en memoria)."""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

from config import get_settings

logger = logging.getLogger(__name__)


def resolve_ffprobe_path() -> str | None:
    s = get_settings()
    if s.ffprobe_path and Path(s.ffprobe_path).exists():
        return s.ffprobe_path
    w = shutil.which("ffprobe")
    if w:
        return w
    # En Windows a veces solo está ffmpeg del mismo bundle.
    if s.ffmpeg_path:
        p = Path(s.ffmpeg_path)
        probe = p.with_name(p.name.replace("ffmpeg", "ffprobe"))
        if probe.exists():
            return str(probe)
    return None


def probe_duration_seconds(video_path: str) -> float | None:
    """Devuelve duración en segundos o None si falla."""
    ffprobe = resolve_ffprobe_path()
    if not ffprobe:
        logger.warning("ffprobe no encontrado; no se puede medir duración del vídeo")
        return None
    try:
        cmd = [
            ffprobe,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            video_path,
        ]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if out.returncode != 0:
            return None
        data: dict[str, Any] = json.loads(out.stdout or "{}")
        fmt = data.get("format") or {}
        d = fmt.get("duration")
        if d is None:
            return None
        return float(d)
    except Exception as e:
        logger.warning("probe_duration_seconds: %s", e)
        return None
