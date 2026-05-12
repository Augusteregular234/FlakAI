"""Selección del detector según configuración."""
from __future__ import annotations

from config import get_settings
from detection.base import EventDetector
from detection.mock_detector import MockEventDetector


def get_detector() -> EventDetector:
    s = get_settings()
    if s.detector_backend == "mock":
        return MockEventDetector()
    raise ValueError(
        f"detector_backend desconocido: {s.detector_backend!r}. "
        "Implementa un detector en detection/ y regístralo aquí."
    )
