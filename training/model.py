"""
EventClassifier — MobileNetV3-Small backbone (frozen) + temporal mean-pool + MLP.

Architecture:
  Input : [B, T, 3, 224, 224]  T=16 frames sampled from a clip
  Stage1: frozen backbone → 576-d frame features → mean-pool → [B, 576]
  Stage2: MLP 576 → 256 → 128 → 5 classes

Classes: 0=negative  1=goal  2=corner  3=throw_in  4=foul

Training stages:
  Stage 1 (< 200 examples/class): freeze backbone, train head only. Seconds per epoch.
  Stage 2 (200+ examples/class): unfreeze backbone, train end-to-end with lower LR.
"""
from __future__ import annotations

import logging
from pathlib import Path

import torch
import torch.nn as nn

logger = logging.getLogger(__name__)

CLASSES = ["negative", "goal", "corner", "throw_in", "foul"]
NUM_CLASSES = len(CLASSES)
CLASS_TO_IDX: dict[str, int] = {c: i for i, c in enumerate(CLASSES)}
IDX_TO_CLASS: dict[int, str] = {i: c for i, c in enumerate(CLASSES)}
BACKBONE_DIM = 576


def _build_backbone() -> tuple[nn.Module, int]:
    """Returns (backbone, out_dim). Works with torchvision >= 0.13."""
    import torchvision.models as tv

    try:
        from torchvision.models import MobileNet_V3_Small_Weights
        weights = MobileNet_V3_Small_Weights.IMAGENET1K_V1
        net = tv.mobilenet_v3_small(weights=weights)
    except ImportError:
        net = tv.mobilenet_v3_small(pretrained=True)

    # Remove classification head; keep feature extractor + global pool
    backbone = nn.Sequential(net.features, net.avgpool)
    return backbone, BACKBONE_DIM


class EventClassifier(nn.Module):
    """
    Frame-level feature extractor + temporal mean-pool + event classifier.

    freeze_backbone=True  → train only the MLP head (fast, few examples needed)
    freeze_backbone=False → full fine-tuning (more data, lower LR)
    """

    def __init__(self, freeze_backbone: bool = True, dropout: float = 0.35):
        super().__init__()
        self.backbone, out_dim = _build_backbone()

        if freeze_backbone:
            for p in self.backbone.parameters():
                p.requires_grad = False

        self.head = nn.Sequential(
            nn.Flatten(),
            nn.Linear(out_dim, 256),
            nn.Hardswish(),
            nn.Dropout(p=dropout),
            nn.Linear(256, 128),
            nn.Hardswish(),
            nn.Dropout(p=dropout * 0.5),
            nn.Linear(128, NUM_CLASSES),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: [B, T, C, H, W] → logits [B, NUM_CLASSES]"""
        B, T = x.shape[:2]
        frames = x.view(B * T, *x.shape[2:])    # [B*T, C, H, W]
        feats = self.backbone(frames)             # [B*T, 576, 1, 1]
        feats = feats.view(B, T, -1).mean(dim=1) # [B, 576]  temporal mean-pool
        return self.head(feats)

    def predict_proba(self, x: torch.Tensor) -> torch.Tensor:
        """Softmax probabilities. No grad."""
        self.eval()
        with torch.no_grad():
            return torch.softmax(self.forward(x), dim=-1)

    def unfreeze_backbone(self, lr_scale: float = 0.1) -> list[dict]:
        """
        Unfreeze backbone for stage-2 fine-tuning.
        Returns param groups: backbone with scaled LR, head with full LR.
        """
        for p in self.backbone.parameters():
            p.requires_grad = True
        return [
            {"params": self.backbone.parameters(), "lr_scale": lr_scale},
            {"params": self.head.parameters(), "lr_scale": 1.0},
        ]


def create_model(freeze_backbone: bool = True) -> EventClassifier:
    return EventClassifier(freeze_backbone=freeze_backbone)


def load_checkpoint(path: str | Path) -> tuple[EventClassifier, dict]:
    """Load checkpoint. Returns (model, metadata_dict)."""
    ckpt = torch.load(str(path), map_location="cpu", weights_only=False)
    model = EventClassifier(freeze_backbone=ckpt.get("freeze_backbone", True))
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()
    logger.info("Loaded checkpoint %s  val_f1=%.3f", path, ckpt.get("val_f1", 0))
    return model, ckpt


def save_checkpoint(
    path: str | Path,
    model: EventClassifier,
    epoch: int,
    metrics: dict,
    freeze_backbone: bool,
) -> None:
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "epoch": epoch,
            "freeze_backbone": freeze_backbone,
            **metrics,
        },
        str(path),
    )
    logger.info("Saved checkpoint %s  epoch=%d  val_f1=%.3f", path, epoch, metrics.get("val_f1", 0))
