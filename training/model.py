"""
EventClassifier — arquitectura modular con backbone, pooling y head intercambiables.

Cada componente se puede sustituir de forma independiente:

  build_backbone("mobilenet_v3_small")   → cualquier torchvision backbone
  build_pooling("mean")                  → mean | attention | lstm | transformer
  build_head("mlp", in_dim, n_classes)   → mlp | linear | deep_mlp

Guardar/cargar checkpoints serializa el nombre de cada componente para
que load_checkpoint reconstruya el modelo exacto sin conocerlo de antemano.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

import torch
import torch.nn as nn

logger = logging.getLogger(__name__)

CLASSES = ["negative", "goal", "corner", "throw_in", "foul", "goal_kick", "shot_on_target"]
NUM_CLASSES = len(CLASSES)
CLASS_TO_IDX: dict[str, int] = {c: i for i, c in enumerate(CLASSES)}
IDX_TO_CLASS: dict[int, str] = {i: c for i, c in enumerate(CLASSES)}

BackboneName = Literal["mobilenet_v3_small", "efficientnet_b2", "efficientnet_b3", "resnet50", "convnext_tiny"]
PoolingName  = Literal["mean", "attention", "lstm", "transformer"]
HeadName     = Literal["mlp", "linear", "deep_mlp"]


# ── Backbones ────────────────────────────────────────────────────────────────

def build_backbone(name: BackboneName = "mobilenet_v3_small") -> tuple[nn.Module, int]:
    """
    Returns (feature_extractor, out_dim).
    out_dim is the flat feature dimension after global average pool.
    """
    import torchvision.models as tv

    def _weights(cls):
        try:
            return cls.IMAGENET1K_V1
        except Exception:
            return None

    if name == "mobilenet_v3_small":
        from torchvision.models import MobileNet_V3_Small_Weights
        net = tv.mobilenet_v3_small(weights=_weights(MobileNet_V3_Small_Weights))
        backbone = nn.Sequential(net.features, net.avgpool)
        return backbone, 576

    if name == "efficientnet_b2":
        from torchvision.models import EfficientNet_B2_Weights
        net = tv.efficientnet_b2(weights=_weights(EfficientNet_B2_Weights))
        backbone = nn.Sequential(net.features, net.avgpool)
        return backbone, 1408

    if name == "efficientnet_b3":
        from torchvision.models import EfficientNet_B3_Weights
        net = tv.efficientnet_b3(weights=_weights(EfficientNet_B3_Weights))
        backbone = nn.Sequential(net.features, net.avgpool)
        return backbone, 1536

    if name == "resnet50":
        from torchvision.models import ResNet50_Weights
        net = tv.resnet50(weights=_weights(ResNet50_Weights))
        backbone = nn.Sequential(*list(net.children())[:-1])  # remove FC
        return backbone, 2048

    if name == "convnext_tiny":
        from torchvision.models import ConvNeXt_Tiny_Weights
        net = tv.convnext_tiny(weights=_weights(ConvNeXt_Tiny_Weights))
        backbone = nn.Sequential(net.features, net.avgpool)
        return backbone, 768

    raise ValueError(f"Unknown backbone: {name!r}")


# ── Temporal pooling ─────────────────────────────────────────────────────────

class MeanPool(nn.Module):
    """Simple temporal mean — fast, works with any data size."""
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x.mean(dim=1)  # [B, T, D] → [B, D]


class AttentionPool(nn.Module):
    """
    Learned temporal attention — weights each frame differently.
    Outperforms mean-pool when some frames are more discriminative than others.
    """
    def __init__(self, in_dim: int):
        super().__init__()
        self.attn = nn.Sequential(nn.Linear(in_dim, 128), nn.Tanh(), nn.Linear(128, 1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: [B, T, D]
        w = torch.softmax(self.attn(x), dim=1)  # [B, T, 1]
        return (x * w).sum(dim=1)               # [B, D]


class LSTMPool(nn.Module):
    """
    Bidirectional LSTM over frames — captures temporal order.
    Recommended when you have 500+ examples per class.
    """
    def __init__(self, in_dim: int, hidden: int = 256):
        super().__init__()
        self.lstm = nn.LSTM(in_dim, hidden, batch_first=True, bidirectional=True)
        self.out_dim = hidden * 2

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        _, (h, _) = self.lstm(x)          # h: [2, B, hidden]
        return torch.cat([h[0], h[1]], dim=-1)  # [B, hidden*2]


class TransformerPool(nn.Module):
    """
    Lightweight Transformer encoder over frames.
    Best accuracy, needs the most data (1000+ examples).
    """
    def __init__(self, in_dim: int, nhead: int = 4, layers: int = 2):
        super().__init__()
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=in_dim, nhead=nhead, dim_feedforward=in_dim * 2,
            dropout=0.1, batch_first=True,
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=layers)
        self.out_dim = in_dim

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.encoder(x).mean(dim=1)  # [B, D]


def build_pooling(name: PoolingName, in_dim: int) -> tuple[nn.Module, int]:
    """Returns (pooling_module, out_dim)."""
    if name == "mean":
        return MeanPool(), in_dim
    if name == "attention":
        return AttentionPool(in_dim), in_dim
    if name == "lstm":
        m = LSTMPool(in_dim)
        return m, m.out_dim
    if name == "transformer":
        m = TransformerPool(in_dim)
        return m, m.out_dim
    raise ValueError(f"Unknown pooling: {name!r}")


# ── Classification heads ──────────────────────────────────────────────────────

def build_head(name: HeadName, in_dim: int, n_classes: int, dropout: float = 0.35) -> nn.Module:
    """
    linear    — logistic regression on features (few examples, strong baseline)
    mlp       — 2-layer MLP (default, good up to ~500 examples)
    deep_mlp  — 3-layer MLP with residual (500+ examples, complex patterns)
    """
    if name == "linear":
        return nn.Linear(in_dim, n_classes)

    if name == "mlp":
        return nn.Sequential(
            nn.Linear(in_dim, 256), nn.Hardswish(), nn.Dropout(dropout),
            nn.Linear(256, 128),   nn.Hardswish(), nn.Dropout(dropout * 0.5),
            nn.Linear(128, n_classes),
        )

    if name == "deep_mlp":
        return nn.Sequential(
            nn.Linear(in_dim, 512), nn.GELU(), nn.Dropout(dropout),
            nn.Linear(512, 256),    nn.GELU(), nn.Dropout(dropout * 0.5),
            nn.Linear(256, 128),    nn.GELU(),
            nn.Linear(128, n_classes),
        )

    raise ValueError(f"Unknown head: {name!r}")


# ── Main model ────────────────────────────────────────────────────────────────

class EventClassifier(nn.Module):
    """
    Fully modular event classifier.

    All three components are pluggable at construction time and serialized
    in the checkpoint so load_checkpoint reconstructs the exact architecture.

    Default (small dataset):
        backbone="mobilenet_v3_small", pooling="mean", head="mlp"

    When to upgrade:
        200+ clips  → pooling="attention"
        500+ clips  → backbone="efficientnet_b3", pooling="attention", head="deep_mlp"
        1000+ clips → pooling="transformer" (with unfrozen backbone)
    """

    def __init__(
        self,
        backbone: BackboneName = "mobilenet_v3_small",
        pooling:  PoolingName  = "mean",
        head:     HeadName     = "mlp",
        freeze_backbone: bool  = True,
        dropout: float         = 0.35,
        n_classes: int         = NUM_CLASSES,
    ):
        super().__init__()
        self.backbone_name = backbone
        self.pooling_name  = pooling
        self.head_name     = head
        self.freeze_backbone_flag = freeze_backbone

        self.backbone_mod, feat_dim = build_backbone(backbone)
        self.pooling_mod,  pool_dim = build_pooling(pooling, feat_dim)
        self.head_mod = build_head(head, pool_dim, n_classes, dropout)

        if freeze_backbone:
            for p in self.backbone_mod.parameters():
                p.requires_grad = False

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: [B, T, C, H, W] → logits [B, n_classes]"""
        B, T = x.shape[:2]
        frames = x.view(B * T, *x.shape[2:])
        feats  = self.backbone_mod(frames)          # [B*T, D, 1, 1] or [B*T, D]
        feats  = feats.view(B, T, -1)               # [B, T, D]
        pooled = self.pooling_mod(feats)            # [B, pool_dim]
        return self.head_mod(pooled)

    def predict_proba(self, x: torch.Tensor) -> torch.Tensor:
        self.eval()
        with torch.no_grad():
            return torch.softmax(self.forward(x), dim=-1)

    def unfreeze_backbone(self) -> None:
        for p in self.backbone_mod.parameters():
            p.requires_grad = True
        self.freeze_backbone_flag = False
        logger.info("Backbone unfrozen for end-to-end fine-tuning.")

    def architecture_summary(self) -> dict:
        trainable = sum(p.numel() for p in self.parameters() if p.requires_grad)
        total     = sum(p.numel() for p in self.parameters())
        return {
            "backbone": self.backbone_name,
            "pooling":  self.pooling_name,
            "head":     self.head_name,
            "freeze_backbone": self.freeze_backbone_flag,
            "trainable_params": trainable,
            "total_params": total,
        }


# ── Factory & persistence ────────────────────────────────────────────────────

def create_model(
    backbone: BackboneName = "mobilenet_v3_small",
    pooling:  PoolingName  = "mean",
    head:     HeadName     = "mlp",
    freeze_backbone: bool  = True,
) -> EventClassifier:
    m = EventClassifier(backbone=backbone, pooling=pooling, head=head,
                        freeze_backbone=freeze_backbone)
    info = m.architecture_summary()
    logger.info("Model created: %s", info)
    return m


def load_checkpoint(path: str | Path) -> tuple[EventClassifier, dict]:
    ckpt = torch.load(str(path), map_location="cpu", weights_only=False)
    model = EventClassifier(
        backbone=ckpt.get("backbone", "mobilenet_v3_small"),
        pooling =ckpt.get("pooling",  "mean"),
        head    =ckpt.get("head",     "mlp"),
        freeze_backbone=ckpt.get("freeze_backbone", True),
    )
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()
    logger.info("Loaded checkpoint %s  arch=%s/%s/%s  val_f1=%.3f",
                Path(path).name,
                ckpt.get("backbone","?"), ckpt.get("pooling","?"), ckpt.get("head","?"),
                ckpt.get("val_f1", 0))
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
            "backbone": model.backbone_name,
            "pooling":  model.pooling_name,
            "head":     model.head_name,
            "epoch": epoch,
            "freeze_backbone": freeze_backbone,
            **metrics,
        },
        str(path),
    )
    logger.info("Saved checkpoint %s  epoch=%d  val_f1=%.3f",
                Path(path).name, epoch, metrics.get("val_f1", 0))
