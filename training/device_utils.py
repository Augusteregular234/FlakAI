"""
Device selection for training.

Priority: cuda (NVIDIA) > dml (AMD/Intel DirectML) > cpu
AMD GPU on Windows requires a Python 3.12 venv with torch-directml.
See training/setup_directml.bat for setup instructions.
"""
from __future__ import annotations
import logging
import os

logger = logging.getLogger(__name__)


def get_device(device_arg: str = "auto"):
    """
    Resolve the best available compute device.

    device_arg values:
      auto  — try cuda, then dml, then cpu
      cuda  — force NVIDIA CUDA (error if unavailable)
      dml   — force AMD/Intel DirectML (error if unavailable)
      cpu   — force CPU
    """
    import torch

    if device_arg == "cpu":
        _set_cpu_threads()
        return torch.device("cpu")

    if device_arg == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but not available (is this an NVIDIA GPU?)")
        dev = torch.device("cuda")
        logger.info("Device: CUDA — %s", torch.cuda.get_device_name(0))
        return dev

    if device_arg == "dml":
        try:
            import torch_directml
            dev = torch_directml.device()
            logger.info("Device: DirectML (AMD/Intel GPU via DirectX 12)")
            return dev
        except ImportError:
            raise RuntimeError(
                "DirectML requested but torch-directml is not installed.\n"
                "Run training/setup_directml.bat to create a Python 3.12 venv with DirectML support."
            )

    # auto: cuda > dml > cpu
    import torch
    if torch.cuda.is_available():
        dev = torch.device("cuda")
        logger.info("Device: CUDA — %s (auto)", torch.cuda.get_device_name(0))
        return dev

    try:
        import torch_directml
        dev = torch_directml.device()
        logger.info("Device: DirectML — AMD/Intel GPU via DirectX 12 (auto)")
        return dev
    except ImportError:
        pass

    _set_cpu_threads()
    n = os.cpu_count() or 1
    logger.info("Device: CPU (%d threads)", n)
    return torch.device("cpu")


def _set_cpu_threads():
    import torch
    n = os.cpu_count() or 1
    torch.set_num_threads(n)
