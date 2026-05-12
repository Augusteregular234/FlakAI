"""Endpoints internos para ML / dataset (solo administradores)."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

import models
from auth import get_current_admin
from config import get_settings, manifest_path_resolved

router = APIRouter(prefix="/api/admin/ml", tags=["ml-admin"])

_VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


@router.get("/summary")
def ml_summary(_: models.User = Depends(get_current_admin)):
    s = get_settings()
    root = Path(s.dataset_videos_dir)
    files: list[Path] = []
    if root.is_dir():
        for p in root.rglob("*"):
            if p.is_file() and p.suffix.lower() in _VIDEO_EXT:
                files.append(p)
    total_bytes = sum(f.stat().st_size for f in files) if files else 0
    mp = manifest_path_resolved()
    return {
        "detector_backend": s.detector_backend,
        "model_version": s.model_version,
        "dataset_videos_dir": str(root),
        "dataset_dir_exists": root.is_dir(),
        "video_file_count": len(files),
        "total_bytes": total_bytes,
        "manifest_path": str(mp),
        "manifest_exists": mp.is_file(),
        "clip_window_seconds": s.clip_window_seconds,
        "auto_approve_confidence": s.auto_approve_confidence,
    }
