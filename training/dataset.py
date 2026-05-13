"""
PyTorch Dataset for event classification.
Loads labeled clips directly from the SQLite DB or from a JSONL export.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Optional

import torch
from torch.utils.data import Dataset

logger = logging.getLogger(__name__)

# Ensure backend is importable
_BACKEND = Path(__file__).parent.parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from training.model import CLASS_TO_IDX, CLASSES
from training.features import extract_frames, N_FRAMES


# ---------------------------------------------------------------------------
# Sample container
# ---------------------------------------------------------------------------

class ClipSample:
    __slots__ = ("clip_path", "label_idx", "event_type", "confidence", "clip_id")

    def __init__(
        self,
        clip_path: str,
        label_idx: int,
        event_type: str,
        confidence: float = 0.0,
        clip_id: int = -1,
    ):
        self.clip_path = clip_path
        self.label_idx = label_idx
        self.event_type = event_type
        self.confidence = confidence
        self.clip_id = clip_id

    def __repr__(self) -> str:
        return f"ClipSample(path={Path(self.clip_path).name!r}, label={CLASSES[self.label_idx]})"


# ---------------------------------------------------------------------------
# DB / JSONL loaders
# ---------------------------------------------------------------------------

def load_from_db(db_path: str | None = None) -> list[ClipSample]:
    """
    Query all reviewed (approved + rejected) clips from the SQLite DB.
    approved → label = event_type class
    rejected → label = 0 (negative)
    """
    from database import SessionLocal, engine
    import models as m

    db = SessionLocal()
    try:
        rows = (
            db.query(m.EventClip)
            .filter(m.EventClip.review_status.in_([
                m.ReviewStatus.approved, m.ReviewStatus.rejected,
            ]))
            .all()
        )
    finally:
        db.close()

    samples = []
    skipped = 0
    for clip in rows:
        if not clip.clip_path or not Path(clip.clip_path).exists():
            skipped += 1
            continue

        if clip.review_status == m.ReviewStatus.approved:
            label = CLASS_TO_IDX.get(clip.event_type.value, 0)
        else:  # rejected → negative
            label = 0

        samples.append(ClipSample(
            clip_path=clip.clip_path,
            label_idx=label,
            event_type=clip.event_type.value,
            confidence=clip.confidence,
            clip_id=clip.id,
        ))

    logger.info(
        "load_from_db: %d samples (%d skipped missing clips). Labels: %s",
        len(samples), skipped,
        {CLASSES[i]: sum(1 for s in samples if s.label_idx == i) for i in range(len(CLASSES))},
    )
    return samples


def load_from_jsonl(jsonl_path: str | Path) -> list[ClipSample]:
    """Load from exported JSONL (api.exportLabels.*)."""
    samples = []
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            clip_path = row.get("clip_path", "")
            if not clip_path or not Path(clip_path).exists():
                continue
            if row.get("training_role") == "positive":
                label = CLASS_TO_IDX.get(row.get("event_type", ""), 0)
            else:
                label = 0
            samples.append(ClipSample(
                clip_path=clip_path,
                label_idx=label,
                event_type=row.get("event_type", "negative"),
                confidence=float(row.get("model_confidence", 0)),
            ))
    logger.info("load_from_jsonl: %d samples from %s", len(samples), jsonl_path)
    return samples


# ---------------------------------------------------------------------------
# Train / val split
# ---------------------------------------------------------------------------

def make_splits(
    samples: list[ClipSample],
    val_ratio: float = 0.2,
    seed: int = 42,
) -> tuple[list[ClipSample], list[ClipSample]]:
    """Stratified train/val split."""
    from sklearn.model_selection import train_test_split

    if len(samples) < 4:
        return samples, []

    labels = [s.label_idx for s in samples]
    try:
        train, val = train_test_split(
            samples, test_size=val_ratio, stratify=labels, random_state=seed
        )
    except ValueError:
        # Fallback if a class has only 1 example
        train, val = train_test_split(samples, test_size=val_ratio, random_state=seed)
    return train, val


def compute_class_weights(samples: list[ClipSample], num_classes: int) -> torch.Tensor:
    """Inverse-frequency class weights for WeightedRandomSampler."""
    from collections import Counter
    counts = Counter(s.label_idx for s in samples)
    weights = torch.zeros(num_classes)
    for i in range(num_classes):
        weights[i] = 1.0 / max(counts.get(i, 1), 1)
    return weights / weights.sum()


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class ClipDataset(Dataset):
    def __init__(self, samples: list[ClipSample], augment: bool = False):
        self.samples = samples
        self.augment = augment

        if augment:
            from torchvision import transforms
            self._aug = transforms.Compose([
                transforms.RandomHorizontalFlip(),
                transforms.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.2),
            ])
        else:
            self._aug = None

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, int]:
        s = self.samples[idx]
        frames = extract_frames(s.clip_path)  # [T, 3, H, W] or None
        if frames is None:
            # Return zero tensor if extraction fails (will be filtered by collate)
            frames = torch.zeros(N_FRAMES, 3, 224, 224)

        if self.augment and self._aug is not None:
            # Apply augmentation to each frame independently
            augmented = []
            for frame in frames:
                # Convert to PIL for transforms, back to tensor
                from torchvision.transforms.functional import to_pil_image, to_tensor
                from training.features import IMAGENET_NORMALIZE
                pil = to_pil_image(frame.mul(torch.tensor([0.229, 0.224, 0.225]).view(3,1,1))
                                       .add(torch.tensor([0.485, 0.456, 0.406]).view(3,1,1)).clamp(0,1))
                pil = self._aug(pil)
                frame_t = IMAGENET_NORMALIZE(to_tensor(pil))
                augmented.append(frame_t)
            frames = torch.stack(augmented)

        return frames, s.label_idx
