#!/usr/bin/env python3
"""
Incremental fine-tuning on newly reviewed clips since the last training run.

Loads existing checkpoint, fine-tunes on new examples only, saves new version.

Usage:
  backend/venv/Scripts/python training/incremental_train.py
  backend/venv/Scripts/python training/incremental_train.py --epochs 5 --lr 1e-4
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("incremental_train")


def run(args: argparse.Namespace) -> dict:
    from training.model import load_checkpoint, save_checkpoint, CLASSES, NUM_CLASSES
    from training.dataset import load_from_db, make_splits, ClipDataset, compute_class_weights
    from training.evaluate import evaluate_model
    from training.train import next_version

    models_dir = REPO / "models"
    checkpoints_dir = REPO / "checkpoints"
    models_dir.mkdir(exist_ok=True)
    checkpoints_dir.mkdir(exist_ok=True)

    # ── Load existing checkpoint ──────────────────────────────────────────
    active_ptr = models_dir / "active_model.txt"
    if args.base_model:
        base_path = Path(args.base_model)
    elif active_ptr.exists():
        base_path = Path(active_ptr.read_text().strip())
    else:
        existing = sorted(models_dir.glob("event_classifier_v*.pt"))
        if not existing:
            logger.error("No existing model. Run training/train.py first.")
            return {"error": "no_base_model"}
        base_path = existing[-1]

    logger.info("Base model: %s", base_path)
    model, ckpt_meta = load_checkpoint(base_path)
    base_version = ckpt_meta.get("version", 0)

    # ── Find new samples (reviewed after last training) ───────────────────
    all_samples = load_from_db()
    if not all_samples:
        logger.warning("No reviewed clips found.")
        return {"error": "no_data", "samples": 0}

    # Filter to samples newer than last training if we have a clip_id watermark
    last_clip_id = ckpt_meta.get("last_clip_id", 0)
    new_samples = [s for s in all_samples if s.clip_id > last_clip_id]

    if len(new_samples) < args.min_new:
        logger.info(
            "Only %d new samples (need %d). Use --min-new to lower threshold.",
            len(new_samples), args.min_new,
        )
        # Still train on all data if forced
        if not args.force:
            return {"info": "too_few_new", "new_samples": len(new_samples)}
        new_samples = all_samples

    logger.info("New samples: %d (total in DB: %d)", len(new_samples), len(all_samples))
    counts = {CLASSES[i]: sum(1 for s in new_samples if s.label_idx == i) for i in range(NUM_CLASSES)}
    logger.info("New samples distribution: %s", counts)

    # ── Train on new samples ──────────────────────────────────────────────
    train_s, val_s = make_splits(new_samples, val_ratio=args.val_ratio)
    if not val_s:
        val_s = all_samples  # fallback to all data for validation

    train_ds = ClipDataset(train_s, augment=True)
    val_ds = ClipDataset(val_s, augment=False)

    cw = compute_class_weights(train_s, NUM_CLASSES)
    weights = torch.tensor([cw[s.label_idx].item() for s in train_s])
    sampler = WeightedRandomSampler(weights, num_samples=len(train_s), replacement=True)

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, sampler=sampler, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, num_workers=0)

    device = torch.device("cuda" if torch.cuda.is_available() and not args.cpu else "cpu")
    model = model.to(device)

    optimizer = torch.optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=args.lr, weight_decay=1e-4,
    )
    loss_wts = (1.0 / (cw + 1e-8)).to(device)
    criterion = nn.CrossEntropyLoss(weight=loss_wts / loss_wts.sum() * NUM_CLASSES)

    best_f1 = -1.0
    best_state = None

    for epoch in range(1, args.epochs + 1):
        model.train()
        total_loss, correct, total = 0.0, 0, 0
        for frames, labels in train_loader:
            frames, labels = frames.to(device), labels.to(device)
            optimizer.zero_grad()
            loss = criterion(model(frames), labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total_loss += loss.item() * len(labels)
            total += len(labels)

        val_metrics = evaluate_model(model, val_loader, device) if val_loader.dataset else {}
        f1 = val_metrics.get("val_f1", 0.0)
        logger.info("Epoch %d/%d  loss=%.4f  val_f1=%.3f", epoch, args.epochs, total_loss / max(total, 1), f1)

        if f1 > best_f1:
            best_f1 = f1
            best_state = {k: v.clone() for k, v in model.state_dict().items()}

    if best_state:
        model.load_state_dict(best_state)

    # ── Save new version ──────────────────────────────────────────────────
    version = next_version(models_dir)
    out_path = models_dir / f"event_classifier_v{version}.pt"
    last_id = max((s.clip_id for s in new_samples), default=0)
    save_checkpoint(out_path, model, args.epochs, {
        "val_f1": best_f1,
        "base_version": base_version,
        "last_clip_id": last_id,
    }, ckpt_meta.get("freeze_backbone", True))
    (models_dir / "active_model.txt").write_text(str(out_path))

    result = {
        "version": version, "base_version": base_version,
        "new_samples": len(new_samples),
        "best_val_f1": round(best_f1, 4),
        "model_path": str(out_path),
    }
    (models_dir / "incremental_metrics.json").write_text(json.dumps(result, indent=2))
    logger.info("Incremental training done. v%d → v%d  val_f1=%.3f", base_version, version, best_f1)
    return result


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--epochs", type=int, default=10)
    p.add_argument("--lr", type=float, default=5e-4)
    p.add_argument("--batch-size", type=int, default=4, dest="batch_size")
    p.add_argument("--val-ratio", type=float, default=0.2, dest="val_ratio")
    p.add_argument("--min-new", type=int, default=10, dest="min_new",
                   help="Minimum new samples needed to trigger training")
    p.add_argument("--force", action="store_true", help="Train even if min_new not reached")
    p.add_argument("--base-model", default=None, dest="base_model")
    p.add_argument("--cpu", action="store_true")
    return p.parse_args()


if __name__ == "__main__":
    result = run(parse_args())
    print(json.dumps(result, indent=2))
