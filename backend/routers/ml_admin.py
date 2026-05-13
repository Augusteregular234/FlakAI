"""
Admin endpoints for ML training, metrics, and model management.

Endpoints:
  GET  /api/admin/ml/summary          — dataset + config overview
  GET  /api/admin/ml/training/status  — current training job state
  GET  /api/admin/ml/training/metrics — latest training metrics
  GET  /api/admin/ml/training/history — all training runs history
  POST /api/admin/ml/training/start   — start full training
  POST /api/admin/ml/training/incremental — start incremental training
  GET  /api/admin/ml/active-learning  — uncertainty-sorted pending clips
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

import models
from auth import get_current_admin
from config import get_settings, manifest_path_resolved
from database import get_db
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/admin/ml", tags=["ml-admin"])

_VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
REPO = Path(__file__).parent.parent.parent


# ── Dataset + config summary ──────────────────────────────────────────────

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

    # Model info
    active_ptr = REPO / "models" / "active_model.txt"
    active_model = active_ptr.read_text().strip() if active_ptr.exists() else None
    available_models = sorted(
        p.name for p in (REPO / "models").glob("event_classifier_v*.pt")
    ) if (REPO / "models").exists() else []

    return {
        "detector_backend": s.detector_backend,
        "model_version": s.model_version,
        "active_model": active_model,
        "available_models": available_models,
        "dataset_videos_dir": str(root),
        "dataset_dir_exists": root.is_dir(),
        "video_file_count": len(files),
        "total_bytes": total_bytes,
        "manifest_path": str(mp),
        "manifest_exists": mp.is_file(),
        "clip_window_seconds": s.clip_window_seconds,
        "auto_approve_confidence": s.auto_approve_confidence,
        "torch_detection_stride": s.torch_detection_stride,
        "torch_detection_threshold": s.torch_detection_threshold,
    }


# ── Training status & metrics ──────────────────────────────────────────────

@router.get("/training/status")
def training_status(_: models.User = Depends(get_current_admin)):
    from ml.trainer import get_coordinator
    return get_coordinator().get_state()


@router.get("/training/metrics")
def training_metrics(_: models.User = Depends(get_current_admin)):
    from ml.trainer import get_coordinator
    m = get_coordinator().get_metrics()
    if not m:
        return {"info": "No training run completed yet. POST /api/admin/ml/training/start to begin."}
    return m


@router.get("/training/history")
def training_history(_: models.User = Depends(get_current_admin)):
    from ml.trainer import get_coordinator
    return {"history": get_coordinator().get_history()}


# ── Start training ────────────────────────────────────────────────────────

@router.post("/training/start")
async def start_training(
    epochs: int = 20,
    lr: float = 1e-3,
    _: models.User = Depends(get_current_admin),
):
    """
    Start full training from all reviewed clips.
    Runs as a background job — poll /training/status for progress.
    """
    from ml.trainer import get_coordinator
    result = await get_coordinator().start(
        mode="full",
        args=["--epochs", str(epochs), "--lr", str(lr)],
    )
    if "error" in result:
        raise HTTPException(status_code=409, detail=result["error"])
    return result


@router.post("/training/incremental")
async def start_incremental(
    epochs: int = 10,
    min_new: int = 5,
    _: models.User = Depends(get_current_admin),
):
    """
    Incremental fine-tune on newly reviewed clips since last training.
    """
    from ml.trainer import get_coordinator
    result = await get_coordinator().start(
        mode="incremental",
        args=["--epochs", str(epochs), "--min-new", str(min_new), "--force"],
    )
    if "error" in result:
        raise HTTPException(status_code=409, detail=result["error"])
    return result


# ── Active learning: clips sorted by uncertainty ──────────────────────────

@router.get("/active-learning")
def active_learning_queue(
    limit: int = 50,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    """
    Returns pending clips sorted by ascending confidence (most uncertain first).
    These are the clips that benefit most from human review.
    """
    clips = (
        db.query(models.EventClip)
        .filter(models.EventClip.review_status == models.ReviewStatus.pending)
        .order_by(models.EventClip.confidence.asc())  # lowest confidence first
        .limit(limit)
        .all()
    )
    return [
        {
            "id": c.id,
            "video_id": c.video_id,
            "event_type": c.event_type.value,
            "timestamp_seconds": c.timestamp_seconds,
            "confidence": c.confidence,
            "model_version": c.model_version,
            "uncertainty": round(100.0 - c.confidence, 1),
        }
        for c in clips
    ]


# ── Dataset stats for training readiness ─────────────────────────────────

@router.get("/dataset/stats")
def dataset_stats(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    """How many labeled examples per class. Training readiness assessment."""
    from collections import Counter

    approved = db.query(models.EventClip).filter(
        models.EventClip.review_status == models.ReviewStatus.approved
    ).all()

    rejected_count = db.query(models.EventClip).filter(
        models.EventClip.review_status == models.ReviewStatus.rejected
    ).count()

    pending_count = db.query(models.EventClip).filter(
        models.EventClip.review_status == models.ReviewStatus.pending
    ).count()

    approved_by_type = Counter(c.event_type.value for c in approved)
    total_approved = len(approved)

    min_per_class = 20  # minimum for meaningful training
    ready_classes = [t for t, n in approved_by_type.items() if n >= min_per_class]
    can_train = total_approved + rejected_count >= 10

    return {
        "approved_by_type": dict(approved_by_type),
        "total_approved": total_approved,
        "total_rejected": rejected_count,
        "total_pending": pending_count,
        "total_labeled": total_approved + rejected_count,
        "ready_classes": ready_classes,
        "can_train": can_train,
        "min_per_class_needed": min_per_class,
        "recommendation": (
            "Ready to train." if can_train else
            f"Need at least 10 reviewed clips. Have {total_approved + rejected_count}."
        ),
    }
