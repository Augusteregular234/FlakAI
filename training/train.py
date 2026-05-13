#!/usr/bin/env python3
"""
Main training script for EventClassifier.

Usage (from repo root):
  backend/venv/Scripts/python training/train.py
  backend/venv/Scripts/python training/train.py --epochs 30 --lr 3e-3
  backend/venv/Scripts/python training/train.py --from-jsonl path/to/labels.jsonl

Outputs:
  models/event_classifier_v<N>.pt    — best checkpoint
  models/training_metrics.json       — latest metrics
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO))

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, WeightedRandomSampler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("train")


def next_version(models_dir: Path) -> int:
    existing = list(models_dir.glob("event_classifier_v*.pt"))
    nums = []
    for p in existing:
        try:
            nums.append(int(p.stem.split("_v")[-1]))
        except ValueError:
            pass
    return max(nums, default=0) + 1


def run(args: argparse.Namespace) -> dict:
    from training.model import EventClassifier, CLASSES, NUM_CLASSES, save_checkpoint
    from training.dataset import (
        load_from_db, load_from_jsonl, make_splits,
        ClipDataset, compute_class_weights,
    )
    from training.evaluate import evaluate_model

    models_dir = REPO / "models"
    checkpoints_dir = REPO / "checkpoints"
    models_dir.mkdir(exist_ok=True)
    checkpoints_dir.mkdir(exist_ok=True)

    # ── Load data ──────────────────────────────────────────────────────────
    if args.from_jsonl:
        samples = load_from_jsonl(args.from_jsonl)
    else:
        samples = load_from_db()

    if len(samples) == 0:
        logger.error("No training data found. Review some clips first (Aceptar/Rechazar).")
        return {"error": "no_data", "samples": 0}

    logger.info("Dataset: %d clips total", len(samples))
    counts = {CLASSES[i]: sum(1 for s in samples if s.label_idx == i) for i in range(NUM_CLASSES)}
    logger.info("Class distribution: %s", counts)

    if len(samples) < 4:
        logger.error("Need at least 4 reviewed clips to train. Got %d.", len(samples))
        return {"error": "too_few_samples", "samples": len(samples)}

    train_samples, val_samples = make_splits(samples, val_ratio=args.val_ratio)
    logger.info("Split: train=%d  val=%d", len(train_samples), len(val_samples))

    # ── Datasets & Loaders ────────────────────────────────────────────────
    train_ds = ClipDataset(train_samples, augment=True)
    val_ds = ClipDataset(val_samples, augment=False)

    # Weighted sampler for class balance
    cw = compute_class_weights(train_samples, NUM_CLASSES)
    sample_weights = torch.tensor([cw[s.label_idx].item() for s in train_samples])
    sampler = WeightedRandomSampler(sample_weights, num_samples=len(train_samples), replacement=True)

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, sampler=sampler, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, num_workers=0)

    # ── Model ─────────────────────────────────────────────────────────────
    device = torch.device("cuda" if torch.cuda.is_available() and not args.cpu else "cpu")
    logger.info("Device: %s", device)

    freeze = len(samples) < args.unfreeze_after
    model = EventClassifier(
        backbone=args.backbone,
        pooling=args.pooling,
        head=args.head,
        freeze_backbone=freeze,
    ).to(device)
    logger.info("Architecture: backbone=%s  pooling=%s  head=%s  frozen=%s",
                args.backbone, args.pooling, args.head, freeze)

    optimizer = torch.optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=args.lr,
        weight_decay=args.wd,
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    # Class weights for loss (handle imbalance)
    loss_weights = (1.0 / (cw + 1e-8)).to(device)
    loss_weights = loss_weights / loss_weights.sum() * NUM_CLASSES
    criterion = nn.CrossEntropyLoss(weight=loss_weights)

    # ── Training loop ─────────────────────────────────────────────────────
    best_f1 = -1.0
    best_ckpt_path = checkpoints_dir / "best.pt"
    history = []

    for epoch in range(1, args.epochs + 1):
        model.train()
        t0 = time.time()
        total_loss = 0.0
        correct = 0
        total = 0

        for frames, labels in train_loader:
            frames, labels = frames.to(device), labels.to(device)
            optimizer.zero_grad()
            logits = model(frames)
            loss = criterion(logits, labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            total_loss += loss.item() * len(labels)
            correct += (logits.argmax(1) == labels).sum().item()
            total += len(labels)

        scheduler.step()
        train_acc = correct / max(total, 1)
        train_loss = total_loss / max(total, 1)

        # Validation
        val_metrics = {}
        if val_loader.dataset:
            val_metrics = evaluate_model(model, val_loader, device)
        else:
            val_metrics = {"val_acc": train_acc, "val_f1": 0.0, "val_loss": train_loss}

        elapsed = time.time() - t0
        logger.info(
            "Epoch %2d/%d  loss=%.4f  train_acc=%.3f  val_acc=%.3f  val_f1=%.3f  (%.1fs)",
            epoch, args.epochs, train_loss, train_acc,
            val_metrics.get("val_acc", 0), val_metrics.get("val_f1", 0), elapsed,
        )

        epoch_result = {
            "epoch": epoch,
            "train_loss": round(train_loss, 4),
            "train_acc": round(train_acc, 4),
            **{k: round(float(v), 4) for k, v in val_metrics.items()},
        }
        history.append(epoch_result)

        if val_metrics.get("val_f1", 0) > best_f1:
            best_f1 = val_metrics.get("val_f1", 0)
            save_checkpoint(best_ckpt_path, model, epoch, val_metrics, freeze)
            logger.info("  ↑ New best checkpoint (val_f1=%.3f)", best_f1)

    # ── Save final model ───────────────────────────────────────────────────
    version = next_version(models_dir)
    final_path = models_dir / f"event_classifier_v{version}.pt"
    import shutil
    shutil.copy(best_ckpt_path, final_path)
    logger.info("Saved best model → %s", final_path)

    (models_dir / "active_model.txt").write_text(str(final_path))

    # Update persistent dataset state
    last_id = max((s.clip_id for s in samples), default=0)
    state_path = models_dir / "dataset_state.json"
    state = {}
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text())
        except Exception:
            pass
    state.update({
        "last_trained_clip_id": last_id,
        "total_trained_samples": len(samples),
        "last_training_run": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "backbone": args.backbone,
        "pooling": args.pooling,
        "head": args.head,
    })
    state_path.write_text(json.dumps(state, indent=2))

    metrics_out = {
        "version": version,
        "model_path": str(final_path),
        "best_val_f1": round(best_f1, 4),
        "epochs": args.epochs,
        "samples_train": len(train_samples),
        "samples_val": len(val_samples),
        "class_counts": counts,
        "freeze_backbone": freeze,
        "history": history,
    }
    (models_dir / "training_metrics.json").write_text(
        json.dumps(metrics_out, indent=2, ensure_ascii=False)
    )
    logger.info("Training complete. best_val_f1=%.3f  model=v%d", best_f1, version)
    return metrics_out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train EventClassifier")
    p.add_argument("--epochs", type=int, default=20, help="Training epochs")
    p.add_argument("--lr", type=float, default=1e-3, help="Learning rate")
    p.add_argument("--wd", type=float, default=1e-4, help="Weight decay")
    p.add_argument("--batch-size", type=int, default=4, dest="batch_size")
    p.add_argument("--val-ratio", type=float, default=0.2, dest="val_ratio")
    p.add_argument("--unfreeze-after", type=int, default=200, dest="unfreeze_after",
                   help="Unfreeze backbone when total samples >= this")
    p.add_argument("--cpu", action="store_true", help="Force CPU even if GPU available")
    p.add_argument("--from-jsonl", default=None, dest="from_jsonl",
                   help="Load from exported JSONL instead of live DB")
    p.add_argument("--backbone", default="mobilenet_v3_small",
                   choices=["mobilenet_v3_small","efficientnet_b2","efficientnet_b3","resnet50","convnext_tiny"])
    p.add_argument("--pooling", default="mean",
                   choices=["mean","attention","lstm","transformer"])
    p.add_argument("--head", default="mlp",
                   choices=["mlp","linear","deep_mlp"])
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    result = run(args)
    if "error" in result:
        sys.exit(1)
