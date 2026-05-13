"""
Selección del detector según DETECTOR_BACKEND en config/.env:
  mock  — generador simulado (por defecto, no requiere modelo entrenado)
  torch — EventClassifier PyTorch (requiere models/active_model.txt)
  onnx  — EventClassifier ONNX   (requiere models/event_classifier.onnx)
"""
from __future__ import annotations

import logging

from config import get_settings
from detection.base import EventDetector
from detection.mock_detector import MockEventDetector

logger = logging.getLogger(__name__)


def get_detector() -> EventDetector:
    s = get_settings()
    backend = s.detector_backend.lower()

    if backend == "mock":
        return MockEventDetector()

    if backend == "torch":
        try:
            from detection.torch_detector import TorchEventDetector
            return TorchEventDetector(
                stride=s.torch_detection_stride,
                threshold=s.torch_detection_threshold,
                nms_window=s.torch_nms_window,
            )
        except FileNotFoundError as e:
            logger.warning("TorchDetector not ready (%s). Falling back to mock.", e)
            return MockEventDetector()
        except ImportError as e:
            logger.warning("torch not installed (%s). Falling back to mock.", e)
            return MockEventDetector()

    if backend == "onnx":
        try:
            from detection.onnx_detector import ONNXEventDetector
            return ONNXEventDetector(
                stride=s.torch_detection_stride,
                threshold=s.torch_detection_threshold,
                nms_window=s.torch_nms_window,
            )
        except (FileNotFoundError, ImportError) as e:
            logger.warning("ONNXDetector not ready (%s). Falling back to mock.", e)
            return MockEventDetector()

    raise ValueError(
        f"detector_backend desconocido: {backend!r}. "
        "Valores válidos: mock | torch | onnx"
    )
