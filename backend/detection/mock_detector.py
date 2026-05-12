"""
Detector simulado para MVP. Sustituir por modelo real usando los mismos tipos (`RawEvent`).
Los timestamps se escalan a la duración real del vídeo si está disponible.
"""
from __future__ import annotations

import hashlib
import random

import models
from config import get_settings
from detection.base import RawEvent


class MockEventDetector:
    def __init__(self) -> None:
        s = get_settings()
        self.model_version = s.model_version
        self._min_ev = s.mock_events_min
        self._max_ev = s.mock_events_max
        self._gap = s.mock_min_gap_seconds

    def detect(self, video_path: str, duration_seconds: float | None) -> list[RawEvent]:
        s = get_settings()
        h = hashlib.sha256(
            f"{video_path}:{self.model_version}".encode("utf-8")
        ).digest()
        seed = int.from_bytes(h[:8], "big")
        rng = random.Random(seed)

        dur = duration_seconds or 600.0
        margin = float(s.clip_window_seconds) + 5.0
        hi = max(margin + 30.0, dur - margin)
        lo = min(35.0, hi * 0.1)

        n = rng.randint(self._min_ev, self._max_ev)
        used: list[float] = []
        events: list[RawEvent] = []

        event_types = [
            models.EventType.goal,
            models.EventType.corner,
            models.EventType.throw_in,
            models.EventType.foul,
        ]

        for _ in range(n):
            ts = rng.uniform(lo, hi)
            attempts = 0
            while attempts < 80 and any(abs(ts - t) < self._gap for t in used):
                ts = rng.uniform(lo, hi)
                attempts += 1
            used.append(ts)
            events.append(
                RawEvent(
                    event_type=rng.choice(event_types),
                    timestamp_seconds=round(ts, 2),
                    confidence=round(rng.uniform(50.0, 99.0), 1),
                    extra={"backend": "mock"},
                )
            )

        events.sort(key=lambda e: e.timestamp_seconds)
        return events
