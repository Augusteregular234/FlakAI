"""
ONNXEventDetector — same interface as TorchEventDetector but uses ONNX Runtime.
Faster CPU inference, no PyTorch required at runtime.

Requires:
  pip install onnxruntime
  training/export_onnx.py must have been run first.

Set DETECTOR_BACKEND=onnx in backend/.env.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).parent.parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(REPO / "backend") not in sys.path:
    sys.path.insert(0, str(REPO / "backend"))

from detection.base import RawEvent
import models as m

logger = logging.getLogger(__name__)


class ONNXEventDetector:
    """ONNX Runtime-based detector. Same sliding-window approach as TorchEventDetector."""

    def __init__(
        self,
        onnx_path: str | Path | None = None,
        stride: float = 5.0,
        half_window: float = 8.0,
        threshold: float = 40.0,
        nms_window: float = 20.0,
    ):
        try:
            import onnxruntime as ort
        except ImportError:
            raise ImportError(
                "onnxruntime not installed. Run: pip install onnxruntime"
            )

        self.stride = stride
        self.half_window = half_window
        self.threshold = threshold
        self.nms_window = nms_window

        if onnx_path is None:
            onnx_path = REPO / "models" / "event_classifier.onnx"
            if not Path(onnx_path).exists():
                raise FileNotFoundError(
                    f"ONNX model not found at {onnx_path}. "
                    "Run: backend/venv/Scripts/python training/export_onnx.py"
                )

        self._sess = ort.InferenceSession(
            str(onnx_path), providers=["CPUExecutionProvider"]
        )
        self._input_name = self._sess.get_inputs()[0].name
        self.model_version = f"onnx:{Path(onnx_path).name}"

        from training.model import IDX_TO_CLASS
        self._idx_to_event: dict[int, m.EventType] = {}
        for idx, cls in IDX_TO_CLASS.items():
            if idx == 0:
                continue
            try:
                self._idx_to_event[idx] = m.EventType(cls)
            except ValueError:
                pass

        logger.info("ONNXEventDetector loaded: %s", onnx_path)

    def detect(self, video_path: str, duration_seconds: float | None) -> list[RawEvent]:
        from training.features import extract_frames_at_timestamp

        if not Path(video_path).exists():
            return []

        dur = duration_seconds or 5400.0
        candidates = [self.stride * i for i in range(1, int(dur / self.stride) + 1)
                      if self.stride * i < dur - self.half_window]

        raw: list[tuple[float, m.EventType, float]] = []

        for ts in candidates:
            frames = extract_frames_at_timestamp(video_path, ts, n_frames=16, half_window=self.half_window)
            if frames is None:
                continue

            inp = frames.unsqueeze(0).numpy().astype(np.float32)
            logits = self._sess.run(None, {self._input_name: inp})[0][0]  # [5]
            probs = np.exp(logits - logits.max())
            probs /= probs.sum()

            best_idx = int(probs[1:].argmax()) + 1
            best_conf = float(probs[best_idx]) * 100.0

            if best_conf >= self.threshold and best_idx in self._idx_to_event:
                raw.append((ts, self._idx_to_event[best_idx], best_conf))

        events = _nms(raw, self.nms_window, self.model_version)
        logger.info("ONNXDetector: %d raw → %d after NMS", len(raw), len(events))
        return events


def _nms(
    detections: list[tuple[float, m.EventType, float]],
    window: float,
    model_version: str,
) -> list[RawEvent]:
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
            extra={"backend": "onnx", "model_version": model_version},
        ))
        for j, (ts2, et2, _) in enumerate(detections):
            if j != i and j not in suppressed and et2 == et and abs(ts2 - ts) < window:
                suppressed.add(j)
    kept.sort(key=lambda e: e.timestamp_seconds)
    return kept
