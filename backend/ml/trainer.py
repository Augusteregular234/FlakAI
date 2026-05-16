"""
Training coordinator: launches training scripts as detached subprocesses,
tracks state via log file polling, and exposes results to the admin API.

Key design: training runs as a DETACHED process (not a child of uvicorn).
This means uvicorn reloads never kill the training subprocess.
"""
from __future__ import annotations

import asyncio
import json
import logging
import platform
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

_EPOCH_RE = re.compile(
    r"Epoch\s+(\d+)/(\d+).*val_f1=([0-9.]+).*\(([0-9.]+)s\)"
)

logger = logging.getLogger(__name__)

REPO = Path(__file__).parent.parent.parent
MODELS_DIR = REPO / "models"
_DML_PYTHON = REPO / "training" / "training_venv" / "Scripts" / "python.exe"
_CPU_PYTHON  = REPO / "backend"  / "venv"          / "Scripts" / "python.exe"
VENV_PYTHON  = _DML_PYTHON if _DML_PYTHON.exists() else _CPU_PYTHON
STATUS_FILE  = MODELS_DIR / "training_status.json"
METRICS_FILE = MODELS_DIR / "training_metrics.json"
HISTORY_FILE = MODELS_DIR / "training_history.json"
LOG_FILE     = MODELS_DIR / "training_output.log"


@dataclass
class TrainingState:
    status: str = "idle"       # idle | running | done | failed
    started_at: float = 0.0
    finished_at: float = 0.0
    mode: str = ""
    samples: int = 0
    best_val_f1: float = 0.0
    model_version: int = 0
    error: str = ""
    current_epoch: int = 0
    total_epochs: int = 0
    last_val_f1: float = 0.0
    last_epoch_seconds: float = 0.0
    logs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_file(cls) -> "TrainingState":
        MODELS_DIR.mkdir(exist_ok=True)
        if STATUS_FILE.exists():
            try:
                data = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
                # Filter to known fields — handles schema evolution gracefully
                known = set(cls.__dataclass_fields__)
                return cls(**{k: v for k, v in data.items() if k in known})
            except Exception:
                pass
        return cls()

    def save(self) -> None:
        MODELS_DIR.mkdir(exist_ok=True)
        STATUS_FILE.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


_state = TrainingState.from_file()
_lock = asyncio.Lock()


def get_state() -> TrainingState:
    return _state


def get_metrics() -> dict:
    if METRICS_FILE.exists():
        try:
            return json.loads(METRICS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def get_history() -> list[dict]:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _append_history(metrics: dict) -> None:
    history = get_history()
    history.append({"timestamp": time.time(), **metrics})
    HISTORY_FILE.write_text(json.dumps(history[-50:], indent=2), encoding="utf-8")


def _resolve_python() -> str:
    return str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable


def _run_training_sync(mode: str, extra_args: list[str]) -> dict:
    global _state
    python = _resolve_python()
    script = str(REPO / "training" / ("incremental_train.py" if mode == "incremental" else "train.py"))
    cmd = [python, script] + extra_args

    logger.info("Starting training subprocess: %s", " ".join(cmd))
    _state.logs = [f"$ {' '.join(cmd)}"]

    MODELS_DIR.mkdir(exist_ok=True)
    log_file = LOG_FILE
    log_file.write_text("", encoding="utf-8")  # clear previous log

    # Launch as DETACHED process — survives uvicorn reloads
    popen_kwargs: dict = {
        "cwd": str(REPO / "backend"),
        "stdout": open(log_file, "w", encoding="utf-8"),
        "stderr": subprocess.STDOUT,
    }
    if platform.system() == "Windows":
        popen_kwargs["creationflags"] = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        )

    try:
        proc = subprocess.Popen(cmd, **popen_kwargs)
    except Exception as e:
        _state.status = "failed"
        _state.error = str(e)
        _state.finished_at = time.time()
        _state.save()
        return {"error": str(e)}

    # Poll log file while process runs
    last_pos = 0
    while proc.poll() is None:
        time.sleep(3)
        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                f.seek(last_pos)
                chunk = f.read()
                last_pos = f.tell()
            for line in chunk.splitlines():
                line = line.strip()
                if not line:
                    continue
                logger.info("[train] %s", line)
                _state.logs.append(line)
                m = _EPOCH_RE.search(line)
                if m:
                    _state.current_epoch    = int(m.group(1))
                    _state.total_epochs     = int(m.group(2))
                    _state.last_val_f1      = float(m.group(3))
                    _state.last_epoch_seconds = float(m.group(4))
            _state.save()
        except Exception:
            pass

    # Flush remaining log lines
    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            f.seek(last_pos)
            for line in f.read().splitlines():
                if line.strip():
                    _state.logs.append(line.strip())
    except Exception:
        pass

    rc = proc.returncode
    if rc != 0:
        _state.status = "failed"
        _state.error = f"Process exited with code {rc}"
        _state.finished_at = time.time()
        _state.save()
        return {"error": _state.error}

    metrics = get_metrics()
    _state.status = "done"
    _state.finished_at = time.time()
    _state.best_val_f1 = metrics.get("best_val_f1", 0.0)
    _state.model_version = metrics.get("version", 0)
    _state.samples = metrics.get("samples_train", 0) + metrics.get("samples_val", 0)
    _state.save()
    _append_history(metrics)
    return metrics


async def start_training(mode: str = "full", extra_args: list[str] | None = None) -> dict:
    global _state
    async with _lock:
        if _state.status == "running":
            return {"error": "already_running", "started_at": _state.started_at}
        _state = TrainingState(status="running", started_at=time.time(), mode=mode)
        _state.save()

    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _run_training_sync, mode, extra_args or [])
    return {"status": "started", "mode": mode}


class TrainingCoordinator:
    def get_state(self) -> dict:
        return TrainingState.from_file().to_dict()

    def get_metrics(self) -> dict:
        return get_metrics()

    def get_history(self) -> list[dict]:
        return get_history()

    async def start(self, mode: str = "full", args: list[str] | None = None) -> dict:
        return await start_training(mode, args)


def get_coordinator() -> TrainingCoordinator:
    return TrainingCoordinator()
