#!/usr/bin/env python3
"""
Export trained EventClassifier to ONNX for faster CPU inference.

Usage:
  backend/venv/Scripts/python training/export_onnx.py
  backend/venv/Scripts/python training/export_onnx.py --model models/event_classifier_v2.pt --out models/event_classifier.onnx
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO))

import torch

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("export_onnx")


def export(model_path: Path, out_path: Path, n_frames: int = 16) -> Path:
    from training.model import load_checkpoint
    from training.features import N_FRAMES as N_FRAMES_DEFAULT

    logger.info("Loading model from %s", model_path)
    model, ckpt = load_checkpoint(model_path)
    model.eval()

    dummy = torch.zeros(1, n_frames, 3, 224, 224)
    with torch.no_grad():
        _ = model(dummy)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    torch.onnx.export(
        model,
        dummy,
        str(out_path),
        export_params=True,
        opset_version=17,
        do_constant_folding=True,
        input_names=["frames"],
        output_names=["logits"],
        dynamic_axes={
            "frames": {0: "batch_size"},
            "logits": {0: "batch_size"},
        },
    )
    logger.info("Exported ONNX → %s", out_path)

    # Verify
    try:
        import onnxruntime as ort
        sess = ort.InferenceSession(str(out_path), providers=["CPUExecutionProvider"])
        out = sess.run(None, {"frames": dummy.numpy()})
        import numpy as np
        probs = np.exp(out[0]) / np.exp(out[0]).sum(axis=1, keepdims=True)
        logger.info("ONNX inference test OK. Output shape: %s  probs_sum=%.3f", out[0].shape, probs.sum())
    except ImportError:
        logger.warning("onnxruntime not installed — skipping verification. Install with: pip install onnxruntime")
    except Exception as e:
        logger.warning("ONNX verification failed: %s", e)

    meta = {
        "source_model": str(model_path),
        "onnx_path": str(out_path),
        "n_frames": n_frames,
        "opset": 17,
        "checkpoint_epoch": ckpt.get("epoch"),
        "checkpoint_val_f1": ckpt.get("val_f1"),
    }
    (out_path.parent / "onnx_export_meta.json").write_text(json.dumps(meta, indent=2))
    return out_path


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--model", default=None)
    p.add_argument("--out", default=None)
    args = p.parse_args()

    models_dir = REPO / "models"

    if args.model:
        model_path = Path(args.model)
    else:
        active = models_dir / "active_model.txt"
        if active.exists():
            model_path = Path(active.read_text().strip())
        else:
            candidates = sorted(models_dir.glob("event_classifier_v*.pt"))
            if not candidates:
                print("No model found. Run training/train.py first.")
                sys.exit(1)
            model_path = candidates[-1]

    out_path = Path(args.out) if args.out else models_dir / "event_classifier.onnx"
    export(model_path, out_path)
