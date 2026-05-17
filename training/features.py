"""
Frame extraction from video clips using ffmpeg.
No opencv dependency — uses ffmpeg subprocess (already available).
"""
from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import torch
from torchvision import transforms
from PIL import Image

logger = logging.getLogger(__name__)

N_FRAMES = 16
FRAME_SIZE = 224

IMAGENET_NORMALIZE = transforms.Normalize(
    mean=[0.485, 0.456, 0.406],
    std=[0.229, 0.224, 0.225],
)

CLIP_TRANSFORM = transforms.Compose([
    transforms.Resize((FRAME_SIZE, FRAME_SIZE), antialias=True),
    transforms.ToTensor(),
    IMAGENET_NORMALIZE,
])


def _resolve_bins() -> tuple[str, str]:
    """Find ffmpeg/ffprobe binaries from PATH or backend config."""
    import shutil, sys
    ff = shutil.which("ffmpeg")
    fp = shutil.which("ffprobe")
    if ff and fp:
        return ff, fp
    # Try importing from backend
    try:
        backend = Path(__file__).parent.parent / "backend"
        if str(backend) not in sys.path:
            sys.path.insert(0, str(backend))
        from clip_generation import resolve_ffmpeg_path
        from video_probe import resolve_ffprobe_path
        ff = resolve_ffmpeg_path() or ff
        fp = resolve_ffprobe_path() or fp
    except Exception:
        pass
    return ff or "ffmpeg", fp or "ffprobe"


def get_clip_duration(clip_path: str | Path, ffprobe: str = "ffprobe") -> float | None:
    """Returns clip duration in seconds via ffprobe."""
    try:
        r = subprocess.run(
            [ffprobe, "-v", "quiet", "-of", "json", "-show_format", str(clip_path)],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            return None
        data = json.loads(r.stdout)
        return float(data["format"]["duration"])
    except Exception as e:
        logger.debug("get_clip_duration failed for %s: %s", clip_path, e)
        return None


def extract_frames(
    clip_path: str | Path,
    n_frames: int = N_FRAMES,
    size: int = FRAME_SIZE,
    ffmpeg: str | None = None,
    ffprobe: str | None = None,
) -> Optional[torch.Tensor]:
    """
    Sample n_frames uniformly from a clip.
    Returns [n_frames, 3, size, size] float32 tensor (ImageNet-normalized).
    Returns None if clip is missing or extraction fails.
    """
    clip_path = Path(clip_path)
    if not clip_path.exists():
        logger.warning("extract_frames: clip not found %s", clip_path)
        return None

    if ffmpeg is None or ffprobe is None:
        _ff, _fp = _resolve_bins()
        ffmpeg = ffmpeg or _ff
        ffprobe = ffprobe or _fp

    duration = get_clip_duration(str(clip_path), ffprobe)
    if duration is None or duration < 0.2:
        logger.warning("extract_frames: duration %.2f too short for %s", duration or 0, clip_path.name)
        return None

    fps_target = n_frames / duration

    with tempfile.TemporaryDirectory() as tmpdir:
        out_pat = str(Path(tmpdir) / "f%04d.jpg")
        cmd = [
            ffmpeg, "-y",
            "-i", str(clip_path),
            "-vf", f"fps={fps_target:.6f},scale={size}:{size}",
            "-frames:v", str(n_frames),
            "-q:v", "3",
            out_pat,
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=90)
            if r.returncode != 0:
                logger.warning("ffmpeg frame extraction failed for %s: %s",
                               clip_path.name, r.stderr[-200:].decode(errors="replace"))
        except subprocess.TimeoutExpired:
            logger.warning("extract_frames: ffmpeg timeout (>90s), skipping %s", clip_path.name)
            return None

        frames: list[torch.Tensor] = []
        for i in range(1, n_frames + 2):
            fp = Path(tmpdir) / f"f{i:04d}.jpg"
            if fp.exists():
                img = Image.open(fp).convert("RGB")
                frames.append(CLIP_TRANSFORM(img))
            if len(frames) == n_frames:
                break

        if not frames:
            return None

        # Pad with last frame if fewer frames were extracted
        while len(frames) < n_frames:
            frames.append(frames[-1])

        return torch.stack(frames[:n_frames])  # [T, 3, H, W]


def extract_frames_at_timestamp(
    video_path: str | Path,
    timestamp_seconds: float,
    n_frames: int = N_FRAMES,
    half_window: float = 8.0,
    size: int = FRAME_SIZE,
    ffmpeg: str | None = None,
    ffprobe: str | None = None,
) -> Optional[torch.Tensor]:
    """
    Extract n_frames from a video centered on timestamp_seconds.
    window = [timestamp - half_window, timestamp + half_window].
    """
    if ffmpeg is None or ffprobe is None:
        ffmpeg, ffprobe = _resolve_bins()

    video_path = Path(video_path)
    if not video_path.exists():
        return None

    start = max(0.0, timestamp_seconds - half_window)
    duration = half_window * 2.0
    fps_target = n_frames / duration

    with tempfile.TemporaryDirectory() as tmpdir:
        out_pat = str(Path(tmpdir) / "f%04d.jpg")
        cmd = [
            ffmpeg, "-y",
            "-ss", str(start),
            "-i", str(video_path),
            "-t", str(duration),
            "-vf", f"fps={fps_target:.6f},scale={size}:{size}",
            "-frames:v", str(n_frames),
            "-q:v", "3",
            out_pat,
        ]
        subprocess.run(cmd, capture_output=True, timeout=60)

        frames = []
        for i in range(1, n_frames + 2):
            fp = Path(tmpdir) / f"f{i:04d}.jpg"
            if fp.exists():
                img = Image.open(fp).convert("RGB")
                frames.append(CLIP_TRANSFORM(img))
            if len(frames) == n_frames:
                break

        if not frames:
            return None
        while len(frames) < n_frames:
            frames.append(frames[-1])
        return torch.stack(frames[:n_frames])
