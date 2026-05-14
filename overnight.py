"""
Worker autónomo nocturno para FlakAI.
Busca partidos enteros en YouTube, los descarga y los sube para análisis.

Uso:
  python overnight.py

Detener: Ctrl+C
Log: overnight_log.txt
"""
from __future__ import annotations

import logging
import math
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

# ── Config ────────────────────────────────────────────────────────────────────
API          = "http://localhost:8000"
USERNAME     = "admin"
PASSWORD     = "admin"
DEST_DIR     = Path(r"C:\Users\saamu\Videos\analisisFLK")
CHUNK_SIZE   = 5 * 1024 * 1024   # 5 MB
KEEP_FILES   = True               # conservar vídeos descargados
SLEEP_BETWEEN = 30                # segundos entre partidos
MAX_MATCHES  = 40                 # tope de seguridad por noche

LOG_FILE = Path(__file__).parent / "overnight_log.txt"

_handlers: list[logging.Handler] = [logging.FileHandler(LOG_FILE, encoding="utf-8")]
try:
    _sh = logging.StreamHandler(sys.stdout)
    _sh.stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    _handlers.append(_sh)
except Exception:
    pass  # stdout no disponible (proceso oculto)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=_handlers,
)
log = logging.getLogger("overnight")

# ── Partidos a buscar (URLs directas de YouTube con partidos completos conocidos) ──
# Formato: (descripción, url)
MATCH_QUEUE: list[tuple[str, str]] = [
    # Verificados con yt-dlp — todos 78-152 min
    ("Borja vs Barco 90min 2024",                  "https://www.youtube.com/watch?v=pqeoHd6cuJ4"),
    ("Chelsea 2-2 Wrexham Chelsea USA Tour 2024",  "https://www.youtube.com/watch?v=rlAWV1Kelsg"),
    ("Portugal vs Argentina Full Match",           "https://www.youtube.com/watch?v=PTGu-ItQ5Jc"),
    ("Crystal Palace vs Man City FA Cup Final",    "https://www.youtube.com/watch?v=77O3XPsanEo"),
    ("Bournemouth vs Man City FA Cup QF",          "https://www.youtube.com/watch?v=9cGlZNvdCgk"),
    ("Man City vs Plymouth Argyle FA Cup R5",      "https://www.youtube.com/watch?v=Og5BE9c8wKI"),
    ("Brazil vs Costa Rica Copa America 2024",     "https://www.youtube.com/watch?v=sDBHT3Hetus"),
    ("Liverpool vs Everton WSL 2024-25",           "https://www.youtube.com/watch?v=0swt4b-1X_M"),
    ("Notre Dame vs California ACC Soccer 2024",   "https://www.youtube.com/watch?v=Gxxdz8l-WYg"),
]

PYTHON = sys.executable  # el mismo intérprete (ya tiene yt-dlp instalado)


# ── Auth ──────────────────────────────────────────────────────────────────────

def login() -> str | None:
    try:
        r = requests.post(f"{API}/api/auth/login",
                          json={"username": USERNAME, "password": PASSWORD},
                          timeout=10)
        if r.ok:
            log.info("Login OK como '%s'", USERNAME)
            return r.json()["access_token"]
        log.error("Login fallido: %s", r.text)
    except Exception as e:
        log.error("No se puede conectar a la API: %s", e)
    return None


# ── Download ──────────────────────────────────────────────────────────────────

def download(url: str, dest_dir: Path) -> Path | None:
    output_tmpl = str(dest_dir / "%(title).80s.%(ext)s")
    t0 = time.time()

    cmd = [
        PYTHON, "-m", "yt_dlp",
        "--no-playlist",
        "-f", "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "--no-warnings",
        "-o", output_tmpl,
        url,
    ]
    log.info("Descargando: %s", url)
    result = subprocess.run(cmd, timeout=3600, capture_output=False)
    if result.returncode != 0:
        log.warning("yt-dlp fallo (rc=%d) para %s", result.returncode, url)
        return None

    # Buscar el .mp4 mas reciente en dest_dir (nuevo o ya existente/sobreescrito)
    all_mp4 = list(dest_dir.glob("*.mp4"))
    if not all_mp4:
        log.warning("No se encontro .mp4 en %s para %s", dest_dir, url)
        return None

    # Preferir archivo creado/modificado en esta sesion; fallback al mas reciente
    recent = [f for f in all_mp4 if f.stat().st_mtime >= t0 - 10]
    candidates = recent if recent else all_mp4
    path = sorted(candidates, key=lambda f: f.stat().st_mtime, reverse=True)[0]
    size_mb = path.stat().st_size / 1_048_576
    log.info("Listo: %s (%.1f MB)", path.name, size_mb)
    return path


# ── Upload ────────────────────────────────────────────────────────────────────

def upload(token: str, video_path: Path) -> int | None:
    headers = {"Authorization": f"Bearer {token}"}
    file_size = video_path.stat().st_size

    # init
    r = requests.post(f"{API}/api/videos/upload/init",
                      data={"filename": video_path.name, "file_size": str(file_size)},
                      headers=headers, timeout=15)
    if not r.ok:
        log.error("Upload init falló: %s", r.text)
        return None
    upload_id = r.json()["upload_id"]
    video_id  = r.json()["video_id"]

    # chunks
    total = math.ceil(file_size / CHUNK_SIZE)
    log.info("Subiendo %s en %d chunks…", video_path.name, total)
    with open(video_path, "rb") as f:
        for i in range(total):
            data = f.read(CHUNK_SIZE)
            r = requests.post(
                f"{API}/api/videos/upload/{upload_id}/chunk",
                data={"chunk_index": str(i)},
                files={"chunk": (video_path.name, data, "application/octet-stream")},
                headers=headers, timeout=60,
            )
            if not r.ok:
                log.error("Chunk %d falló: %s", i, r.text)
                return None
            if (i + 1) % 10 == 0 or i + 1 == total:
                log.info("  %d/%d chunks (%.0f%%)", i + 1, total, (i + 1) / total * 100)

    # complete
    r = requests.post(f"{API}/api/videos/upload/{upload_id}/complete",
                      headers=headers, timeout=15)
    if not r.ok:
        log.error("Upload complete falló: %s", r.text)
        return None

    log.info("Subido y analizando: video_id=%d (%s)", video_id, video_path.name)
    return video_id


# ── Main loop ─────────────────────────────────────────────────────────────────

def main() -> None:
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    log.info("=" * 60)
    log.info("Worker nocturno FlakAI arrancado")
    log.info("Destino: %s", DEST_DIR)
    log.info("Partidos en cola: %d", len(MATCH_QUEUE))
    log.info("=" * 60)

    token = login()
    if not token:
        log.error("No se pudo autenticar. Abortando.")
        sys.exit(1)

    done = 0
    for desc, url in MATCH_QUEUE:
        if done >= MAX_MATCHES:
            log.info("Límite de %d partidos alcanzado. Fin.", MAX_MATCHES)
            break

        log.info("─" * 50)
        log.info("[%d/%d] %s", done + 1, len(MATCH_QUEUE), desc)

        # Refrescar token cada 5 partidos
        if done > 0 and done % 5 == 0:
            token = login() or token

        video_path = download(url, DEST_DIR)
        if not video_path:
            log.warning("Saltando %s - descarga fallida", desc)
            continue

        video_id = upload(token, video_path)
        if video_id:
            done += 1
            log.info("DONE partido %d completado. Analizando en background.", done)
        else:
            log.warning("FAIL upload fallido para %s", desc)
            continue

        if not KEEP_FILES:
            video_path.unlink(missing_ok=True)

        if done < len(MATCH_QUEUE):
            log.info("Esperando %ds antes del siguiente...", SLEEP_BETWEEN)
            time.sleep(SLEEP_BETWEEN)

    log.info("=" * 60)
    log.info("Worker finalizado. %d partidos subidos.", done)
    log.info("Clips disponibles en revision: http://localhost:3000/dashboard/review")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
