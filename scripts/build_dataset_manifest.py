#!/usr/bin/env python3
"""
Recorre DATASET_VIDEOS_DIR (config), obtiene duración con ffprobe y escribe manifest JSONL.

Uso (desde la raíz del repo):
  python scripts/build_dataset_manifest.py

Requiere ffprobe en PATH o configurar FFPROBE_PATH / FFMPEG_PATH en backend/.env
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

from config import get_settings, manifest_path_resolved  # noqa: E402
from video_probe import probe_duration_seconds  # noqa: E402

_VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


def file_sha256_preview(path: Path, chunk: int = 2**20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        data = f.read(chunk)
        h.update(data)
    return h.hexdigest()[:16]


def main() -> None:
    s = get_settings()
    src = Path(s.dataset_videos_dir)
    out_path = manifest_path_resolved()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not src.is_dir():
        print(f"Aviso: no existe la carpeta {src}", file=sys.stderr)
        print("Configura DATASET_VIDEOS_DIR en backend/.env", file=sys.stderr)

    rows = []
    if src.is_dir():
        for p in sorted(src.rglob("*")):
            if not p.is_file() or p.suffix.lower() not in _VIDEO_EXT:
                continue
            try:
                st = p.stat()
            except OSError:
                continue
            dur = probe_duration_seconds(str(p))
            try:
                rel = str(p.relative_to(src))
            except ValueError:
                rel = p.name
            rows.append(
                {
                    "path": str(p.resolve()),
                    "relative": rel,
                    "bytes": st.st_size,
                    "mtime_iso": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
                    "duration_seconds": dur,
                    "sha256_prefix": file_sha256_preview(p),
                }
            )

    with open(out_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"Manifest escrito: {out_path} ({len(rows)} vídeos)")


if __name__ == "__main__":
    main()
