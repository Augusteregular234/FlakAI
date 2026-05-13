"""
TorchEventDetector — replaces MockEventDetector when a trained model is available.

Uses a sliding-window approach over the full video:
  1. Sample candidate timestamps every STRIDE seconds
  2. Extract 16 frames centered on each timestamp
  3. Run EventClassifier → probabilities for [negative, goal, corner, throw_in, foul]
  4. Keep detections above confidence threshold
  5. Apply per-class NMS (non-maximum suppression) to merge overlapping detections

Set DETECTOR_BACKEND=torch in backend/.env and ensure models/active_model.txt exists.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import torch

REPO = Path(__file__).parent.parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(REPO / "backend") not in sys.path:
    sys.path.insert(0, str(REPO / "backend"))

from detection.base import RawEvent
import models as m

logger = logging.getLogger(__name__)


class TorchEventDetector:
    """
    Sliding-window event detector backed by a trained EventClassifier.

    Args:
        model_path: Path to .pt checkpoint. If None, uses models/active_model.txt.
        stride: Candidate window every N seconds (default 5).
        half_window: Frames extracted ± N seconds around each candidate (default 8).
        threshold: Minimum confidence % to emit an event (default 40%).
        nms_window: Suppress duplicate detections within N seconds (default 20).
    """

    def __init__(
        self,
        model_path: str | Path | None = None,
        stride: float = 5.0,
        half_window: float = 8.0,
        threshold: float = 40.0,
        nms_window: float = 20.0,
    ):
        self.stride = stride
        self.half_window = half_window
        self.threshold = threshold
        self.nms_window = nms_window

        from training.model import load_checkpoint, IDX_TO_CLASS, NUM_CLASSES, CLASSES

        if model_path is None:
            active_ptr = REPO / "models" / "active_model.txt"
            if active_ptr.exists():
                model_path = Path(active_ptr.read_text().strip())
            else:
                candidates = sorted((REPO / "models").glob("event_classifier_v*.pt"))
                if not candidates:
                    raise FileNotFoundError(
                        "No trained model found. Run: "
                        "backend/venv/Scripts/python training/train.py"
                    )
                model_path = candidates[-1]

        self._model, ckpt = load_checkpoint(model_path)
        self._model.eval()
        self.model_version = f"torch-v{ckpt.get('epoch', 0)}-f1{ckpt.get('val_f1', 0):.2f}"

        self._idx_to_event: dict[int, m.EventType] = {}
        for idx, cls in IDX_TO_CLASS.items():
            if idx == 0:
                continue  # negative
            try:
                self._idx_to_event[idx] = m.EventType(cls)
            except ValueError:
                pass

        logger.info("TorchEventDetector loaded: %s", self.model_version)

    def detect(self, video_path: str, duration_seconds: float | None) -> list[RawEvent]:
        from training.features import extract_frames_at_timestamp

        if not Path(video_path).exists():
            logger.warning("TorchDetector: video not found %s", video_path)
            return []

        dur = duration_seconds or 5400.0
        candidates = [self.stride * i for i in range(1, int(dur / self.stride) + 1)
                      if self.stride * i < dur - self.half_window]

        logger.info(
            "TorchDetector: scanning %.0fs video, %d candidates (stride=%.0fs)",
            dur, len(candidates), self.stride,
        )

        raw_detections: list[tuple[float, m.EventType, float]] = []

        for ts in candidates:
            frames = extract_frames_at_timestamp(
                video_path, ts,
                n_frames=16,
                half_window=self.half_window,
            )
            if frames is None:
                continue

            probs = self._model.predict_proba(frames.unsqueeze(0))[0]  # [5]

            # Find best non-negative class
            event_probs = probs[1:]  # ignore negative
            best_idx = event_probs.argmax().item() + 1
            best_conf = float(probs[best_idx]) * 100.0

            if best_conf >= self.threshold and best_idx in self._idx_to_event:
                et = self._idx_to_event[best_idx]
                raw_detections.append((ts, et, best_conf))
                logger.debug(
                    "  → %s @ %.1fs  conf=%.1f%%",
                    et.value, ts, best_conf,
                )

        events = self._nms(raw_detections)
        logger.info(
            "TorchDetector: %d raw → %d after NMS (threshold=%.0f%%)",
            len(raw_detections), len(events), self.threshold,
        )
        return events

    def _nms(
        self,
        detections: list[tuple[float, m.EventType, float]],
    ) -> list[RawEvent]:
        """Per-class NMS: keep highest-confidence detection in each time window."""
        if not detections:
            return []

        detections.sort(key=lambda x: -x[2])
        kept: list[RawEvent] = []
        suppressed = set()

        for i, (ts, et, conf) in enumerate(detections):
            if i in suppressed:
                continue
            kept.append(RawEvent(
                event_type=et,
                timestamp_seconds=round(ts, 2),
                confidence=round(conf, 1),
                extra={"backend": "torch", "model_version": self.model_version},
            ))
            for j, (ts2, et2, _) in enumerate(detections):
                if j != i and j not in suppressed and et2 == et:
                    if abs(ts2 - ts) < self.nms_window:
                        suppressed.add(j)

        kept.sort(key=lambda e: e.timestamp_seconds)
        return kept
