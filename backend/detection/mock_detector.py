"""
Detector simulado. Genera eventos a una tasa realista proporcional a la duración del vídeo.
Para un partido completo de 90 min produce ~80 eventos distribuidos como en un partido real.
Sustituir por modelo real usando los mismos tipos (RawEvent).
"""
from __future__ import annotations

import hashlib
import logging
import random

import models
from config import get_settings
from detection.base import RawEvent

logger = logging.getLogger(__name__)

# Tasa realista de eventos por minuto en un partido de fútbol
_EVENT_RATES: dict[models.EventType, float] = {
    models.EventType.throw_in:       0.42,   # ~38/90 min
    models.EventType.foul:           0.31,   # ~28/90 min
    models.EventType.goal_kick:      0.22,   # ~20/90 min
    models.EventType.corner:         0.12,   # ~11/90 min
    models.EventType.shot_on_target: 0.08,   # ~7/90 min
    models.EventType.goal:           0.04,   # ~3.6/90 min
}
_TOTAL_RATE = sum(_EVENT_RATES.values())   # ~1.19 eventos/min


class MockEventDetector:
    def __init__(self) -> None:
        s = get_settings()
        self.model_version = s.model_version
        self._min_ev = s.mock_events_min
        self._gap = s.mock_min_gap_seconds

    def detect(self, video_path: str, duration_seconds: float | None) -> list[RawEvent]:
        s = get_settings()
        h = hashlib.sha256(
            f"{video_path}:{self.model_version}".encode("utf-8")
        ).digest()
        seed = int.from_bytes(h[:8], "big")
        rng = random.Random(seed)

        dur = duration_seconds or 5400.0  # fallback a 90 min si no hay duración
        dur_minutes = dur / 60.0

        # Escalar al número de eventos realista; mínimo configurable
        n_target = int(dur_minutes * _TOTAL_RATE)
        n = max(self._min_ev, min(n_target, 500))

        logger.info(
            "MockDetector: vídeo=%.1fs (%.1fmin) → objetivo %d eventos",
            dur, dur_minutes, n,
        )

        half_window = float(s.clip_window_seconds) / 2.0
        margin = half_window + 5.0
        lo = min(30.0, dur * 0.02)
        hi = max(lo + 60.0, dur - margin)

        event_types = list(_EVENT_RATES.keys())
        weights = list(_EVENT_RATES.values())

        used: list[float] = []
        events: list[RawEvent] = []

        for _ in range(n):
            ts = rng.uniform(lo, hi)
            attempts = 0
            while attempts < 40 and any(abs(ts - t) < self._gap for t in used):
                ts = rng.uniform(lo, hi)
                attempts += 1
            used.append(ts)

            evt_type: models.EventType = rng.choices(event_types, weights=weights)[0]

            if evt_type == models.EventType.goal:
                conf = rng.uniform(72.0, 99.0)
            elif evt_type == models.EventType.corner:
                conf = rng.uniform(65.0, 98.0)
            elif evt_type == models.EventType.shot_on_target:
                conf = rng.uniform(60.0, 95.0)
            elif evt_type == models.EventType.foul:
                conf = rng.uniform(55.0, 94.0)
            elif evt_type == models.EventType.goal_kick:
                conf = rng.uniform(55.0, 90.0)
            else:
                conf = rng.uniform(50.0, 92.0)

            events.append(
                RawEvent(
                    event_type=evt_type,
                    timestamp_seconds=round(ts, 2),
                    confidence=round(conf, 1),
                    extra={"backend": "mock"},
                )
            )

        events.sort(key=lambda e: e.timestamp_seconds)

        counts = {t.value: sum(1 for e in events if e.event_type == t) for t in event_types}
        logger.info("MockDetector: generados %d eventos — %s", len(events), counts)
        return events
