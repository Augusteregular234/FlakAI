# Model Upgrade Plan

## Current config (< 300 labeled clips)

```
backbone  = mobilenet_v3_small   (2.5M params, frozen)
pooling   = mean
head      = mlp
```

Works fine for small datasets. Backbone frozen = only head trains = no overfitting risk.

---

## When to upgrade

### Step 1 — ~300 labeled clips: switch to attention pooling

```bash
# In admin panel or API:
POST /api/admin/ml/training/start?pooling=attention
```

**Why:** AttentionPool learns which frames matter most per clip (e.g. the ball
crossing the goal line vs generic play). Free accuracy gain, same backbone, no
extra data needed. Cost: ~128 extra parameters.

**How:**
```python
# training/train.py --pooling attention
```

---

### Step 2 — ~800 labeled clips: upgrade backbone to EfficientNet-B2

```
backbone  = efficientnet_b2   (8M params, frozen initially)
pooling   = attention
head      = mlp
```

**Why:** MobileNetV3 extracts 576-dim features. EfficientNet-B2 extracts 1408-dim.
Richer features = better class separation, especially for visually similar events
(corner vs throw-in both happen near sidelines/bylines).

**How:**
```python
# training/train.py --backbone efficientnet_b2 --pooling attention
```

Note: first run with frozen backbone. Unfreeze after val_f1 plateaus (~10 epochs).

---

### Step 3 — ~1500 labeled clips: deep head + unfreeze backbone

```
backbone  = efficientnet_b2   (unfrozen, end-to-end)
pooling   = attention
head      = deep_mlp
lr        = 1e-4  (lower LR for fine-tuning)
```

**Why:** With enough data, fine-tuning the backbone on football-specific frames
outperforms ImageNet features. deep_mlp handles the larger feature space better.

**How:**
```python
# training/train.py --backbone efficientnet_b2 --pooling attention --head deep_mlp --lr 1e-4
# Set unfreeze_after=0 in config to immediately unfreeze
```

---

### Step 4 — 2000+ labeled clips: LSTM or Transformer pooling

```
backbone  = efficientnet_b3 or convnext_tiny
pooling   = lstm   (or transformer if GPU available)
head      = deep_mlp
```

**Why:** LSTMPool captures temporal order (ball trajectory, player movement sequence).
TransformerPool captures long-range frame dependencies. Both require enough data
to learn meaningful temporal patterns — useless below ~1000 samples.

---

## Known pending fix

`CLASSES` in `training/model.py` currently has 5 classes:
```python
CLASSES = ["negative", "goal", "corner", "throw_in", "foul"]
```

**Missing: `goal_kick` and `shot_on_target`** — clips with these event types
get mapped to `label_idx=0` ("negative") during training. This is a bug that
corrupts the dataset.

**Fix when ready to retrain from scratch** (changing NUM_CLASSES breaks existing checkpoints):
```python
CLASSES = ["negative", "goal", "corner", "throw_in", "foul", "goal_kick", "shot_on_target"]
```

Do this at the same time as a backbone upgrade so you start a new model version cleanly.

---

## GPU note

Current setup: AMD Radeon RX 6600 + Python 3.14 = CPU training only.
To enable GPU: install Python 3.12 and run `training/setup_directml.bat`.
See docs for full instructions.
