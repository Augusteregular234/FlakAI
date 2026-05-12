"""Contrato para detectores de eventos (mock, ONNX, API remota, etc.)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import models


@dataclass
class RawEvent:
    event_type: models.EventType
    timestamp_seconds: float
    confidence: float
    extra: dict | None = None


class EventDetector(Protocol):
    model_version: str

    def detect(self, video_path: str, duration_seconds: float | None) -> list[RawEvent]:
        ...
