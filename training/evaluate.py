#!/usr/bin/env python3
"""
Model evaluation: precision, recall, F1, confusion matrix per event type.

Usage:
  backend/venv/Scripts/python training/evaluate.py
  backend/venv/Scripts/python training/evaluate.py --model models/event_classifier_v2.pt
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO))

import torch
from torch.utils.data import DataLoader

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("evaluate")


def evaluate_model(
    model: "torch.nn.Module",
    loader: DataLoader,
    device: "torch.device | None" = None,
) -> dict:
    """
    Run model on loader, return metrics dict.
    Called from train.py during validation.
    """
    from sklearn.metrics import (
        accuracy_score, f1_score, precision_score, recall_score,
        confusion_matrix as sk_confusion_matrix,
    )
    import torch.nn.functional as F

    if device is None:
        device = next(model.parameters()).device

    model.eval()
    all_preds, all_labels, all_losses = [], [], []
    criterion = torch.nn.CrossEntropyLoss()

    with torch.no_grad():
        for frames, labels in loader:
            frames, labels = frames.to(device), labels.to(device)
            logits = model(frames)
            loss = criterion(logits, labels)
            preds = logits.argmax(dim=1)
            all_preds.extend(preds.cpu().tolist())
            all_labels.extend(labels.cpu().tolist())
            all_losses.append(loss.item())

    if not all_labels:
        return {"val_acc": 0.0, "val_f1": 0.0, "val_loss": 0.0}

    acc = accuracy_score(all_labels, all_preds)
    f1_macro = f1_score(all_labels, all_preds, average="macro", zero_division=0)
    f1_weighted = f1_score(all_labels, all_preds, average="weighted", zero_division=0)
    precision = precision_score(all_labels, all_preds, average="macro", zero_division=0)
    recall = recall_score(all_labels, all_preds, average="macro", zero_division=0)
    val_loss = sum(all_losses) / len(all_losses)

    return {
        "val_acc": float(acc),
        "val_f1": float(f1_macro),
        "val_f1_weighted": float(f1_weighted),
        "val_precision": float(precision),
        "val_recall": float(recall),
        "val_loss": float(val_loss),
    }


def full_report(model_path: str | Path | None = None) -> dict:
    """
    Full evaluation report: per-class metrics + confusion matrix.
    Uses the active model if model_path is None.
    """
    from sklearn.metrics import classification_report, confusion_matrix

    from training.model import load_checkpoint, CLASSES, NUM_CLASSES
    from training.dataset import load_from_db, make_splits, ClipDataset

    models_dir = REPO / "models"

    if model_path is None:
        active = models_dir / "active_model.txt"
        if active.exists():
            model_path = active.read_text().strip()
        else:
            checkpoints = sorted(models_dir.glob("event_classifier_v*.pt"))
            if not checkpoints:
                raise FileNotFoundError("No trained model found. Run training/train.py first.")
            model_path = checkpoints[-1]

    logger.info("Evaluating model: %s", model_path)
    model, ckpt_meta = load_checkpoint(model_path)
    device = torch.device("cpu")
    model = model.to(device)

    samples = load_from_db()
    if not samples:
        return {"error": "no_data"}

    _, val_samples = make_splits(samples)
    if not val_samples:
        val_samples = samples  # use all if too small for split

    val_ds = ClipDataset(val_samples, augment=False)
    val_loader = DataLoader(val_ds, batch_size=4, shuffle=False, num_workers=0)

    model.eval()
    all_preds, all_labels = [], []
    with torch.no_grad():
        for frames, labels in val_loader:
            logits = model(frames.to(device))
            all_preds.extend(logits.argmax(1).cpu().tolist())
            all_labels.extend(labels.tolist())

    # Per-class metrics
    report = classification_report(
        all_labels, all_preds,
        labels=list(range(NUM_CLASSES)),
        target_names=CLASSES,
        output_dict=True,
        zero_division=0,
    )

    cm = confusion_matrix(all_labels, all_preds, labels=list(range(NUM_CLASSES))).tolist()

    result = {
        "model": str(model_path),
        "checkpoint_epoch": ckpt_meta.get("epoch", "?"),
        "checkpoint_val_f1": ckpt_meta.get("val_f1", 0),
        "samples_evaluated": len(val_samples),
        "per_class": {cls: {
            "precision": round(report[cls]["precision"], 3),
            "recall": round(report[cls]["recall"], 3),
            "f1": round(report[cls]["f1-score"], 3),
            "support": int(report[cls]["support"]),
        } for cls in CLASSES if cls in report},
        "macro_avg": {k: round(v, 3) for k, v in report.get("macro avg", {}).items()},
        "weighted_avg": {k: round(v, 3) for k, v in report.get("weighted avg", {}).items()},
        "confusion_matrix": {
            "labels": CLASSES,
            "matrix": cm,
        },
    }

    # Print human-readable report
    logger.info("\n%s", classification_report(
        all_labels, all_preds,
        labels=list(range(NUM_CLASSES)),
        target_names=CLASSES,
        zero_division=0,
    ))
    logger.info("Confusion matrix (rows=true, cols=pred):")
    header = "       " + "  ".join(f"{c[:7]:>7}" for c in CLASSES)
    logger.info(header)
    for i, row in enumerate(cm):
        logger.info(f"  {CLASSES[i][:7]:>7}  " + "  ".join(f"{v:>7}" for v in row))

    return result


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--model", default=None)
    args = p.parse_args()
    result = full_report(args.model)
    print(json.dumps(result, indent=2))
