"""Serializa clips revisados a registros listos para JSONL/CSV (entrenamiento / análisis)."""
from __future__ import annotations

from sqlalchemy.orm import Session

import models

# Orden estable para CSV (cabecera incluso sin filas).
EXPORT_FIELDNAMES = [
    "clip_id",
    "video_id",
    "team_id",
    "team_name",
    "video_original_name",
    "video_source_path",
    "clip_path",
    "event_type",
    "timestamp_seconds",
    "model_confidence",
    "review_status",
    "training_role",
    "model_version",
    "detector_metadata",
    "labeling_note",
]


def fetch_reviewed_clips(
    db: Session,
    *,
    team_id: int | None = None,
) -> list[tuple[models.EventClip, models.VideoMatch, models.Team]]:
    """Clips con decisión humana (no pendientes). Opcionalmente filtrados por equipo."""
    q = (
        db.query(models.EventClip, models.VideoMatch, models.Team)
        .join(models.VideoMatch, models.EventClip.video_id == models.VideoMatch.id)
        .join(models.Team, models.EventClip.team_id == models.Team.id)
        .filter(
            models.EventClip.review_status.in_(
                [models.ReviewStatus.approved, models.ReviewStatus.rejected]
            )
        )
    )
    if team_id is not None:
        q = q.filter(models.EventClip.team_id == team_id)
    return q.order_by(models.EventClip.id).all()


def to_training_record(
    clip: models.EventClip,
    video: models.VideoMatch,
    team: models.Team,
) -> dict:
    if clip.review_status == models.ReviewStatus.approved:
        training_role = "positive"
        note = "Humano confirma que el evento propuesto es válido en este clip."
    elif clip.review_status == models.ReviewStatus.rejected:
        training_role = "negative"
        note = "Humano rechaza el clip (falso positivo o clase incorrecta)."
    else:
        training_role = "pending"
        note = ""

    return {
        "clip_id": clip.id,
        "video_id": video.id,
        "team_id": team.id,
        "team_name": team.name,
        "video_original_name": video.original_name,
        "video_source_path": video.file_path,
        "clip_path": clip.clip_path or "",
        "event_type": clip.event_type.value,
        "timestamp_seconds": clip.timestamp_seconds,
        "model_confidence": clip.confidence,
        "review_status": clip.review_status.value,
        "training_role": training_role,
        "model_version": clip.model_version or "",
        "detector_metadata": clip.detector_metadata or "",
        "labeling_note": note,
    }
