"""
Descarga partidos con yt-dlp y los sube al servidor FlakAI para análisis.

Uso:
  python download_and_upload.py --user admin --password TU_PASS URL1 URL2 ...
  python download_and_upload.py --user admin --password TU_PASS --file urls.txt

Requisitos:
  pip install yt-dlp requests

El servidor debe estar corriendo en http://localhost:8000
"""
from __future__ import annotations

import argparse
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

API = "http://localhost:8000"
CHUNK_SIZE = 5 * 1024 * 1024  # 5 MB por chunk


# ── Auth ─────────────────────────────────────────────────────────────────────

def login(username: str, password: str) -> str:
    r = requests.post(f"{API}/api/auth/login", json={"username": username, "password": password})
    if not r.ok:
        sys.exit(f"Login fallido: {r.json().get('detail', r.text)}")
    token = r.json()["access_token"]
    print(f"[auth] Sesión iniciada como '{username}'")
    return token


# ── Download ──────────────────────────────────────────────────────────────────

def download_video(url: str, dest_dir: Path) -> Path | None:
    print(f"\n[download] {url}")
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--no-playlist",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "-o", str(dest_dir / "%(title).80s.%(ext)s"),
        url,
    ]
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"  [!] yt-dlp falló para {url}")
        return None

    # Devuelve el archivo más reciente en dest_dir
    files = sorted(dest_dir.glob("*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        print("  [!] No se encontró archivo .mp4 tras la descarga")
        return None
    return files[0]


# ── Upload ────────────────────────────────────────────────────────────────────

def upload_video(token: str, video_path: Path) -> int | None:
    headers = {"Authorization": f"Bearer {token}"}
    file_size = video_path.stat().st_size
    filename = video_path.name

    print(f"[upload] {filename} ({file_size / 1_048_576:.1f} MB)")

    # 1. Init
    r = requests.post(
        f"{API}/api/videos/upload/init",
        data={"filename": filename, "file_size": str(file_size)},
        headers=headers,
    )
    if not r.ok:
        print(f"  [!] init falló: {r.json().get('detail', r.text)}")
        return None
    upload_id = r.json()["upload_id"]
    video_id = r.json()["video_id"]

    # 2. Chunks
    total_chunks = math.ceil(file_size / CHUNK_SIZE)
    with open(video_path, "rb") as f:
        for i in range(total_chunks):
            data = f.read(CHUNK_SIZE)
            r = requests.post(
                f"{API}/api/videos/upload/{upload_id}/chunk",
                data={"chunk_index": str(i)},
                files={"chunk": (filename, data, "application/octet-stream")},
                headers=headers,
            )
            if not r.ok:
                print(f"  [!] chunk {i} falló: {r.text}")
                return None
            pct = (i + 1) / total_chunks * 100
            print(f"  chunk {i+1}/{total_chunks} ({pct:.0f}%)", end="\r")
    print()

    # 3. Complete
    r = requests.post(f"{API}/api/videos/upload/{upload_id}/complete", headers=headers)
    if not r.ok:
        print(f"  [!] complete falló: {r.json().get('detail', r.text)}")
        return None

    print(f"  ✓ video_id={video_id} — procesando en background")
    return video_id


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Descarga y sube vídeos a FlakAI")
    parser.add_argument("--user", required=True, help="Usuario de FlakAI")
    parser.add_argument("--password", required=True, help="Contraseña")
    parser.add_argument("--api", default="http://localhost:8000", help="URL base de la API")
    parser.add_argument("--keep", action="store_true", help="No borrar vídeos descargados tras subir")
    parser.add_argument("--file", help="Fichero .txt con URLs (una por línea)")
    parser.add_argument("urls", nargs="*", help="URLs de vídeos a descargar")
    args = parser.parse_args()

    global API
    API = args.api

    urls: list[str] = list(args.urls)
    if args.file:
        fp = Path(args.file)
        if not fp.exists():
            sys.exit(f"Fichero no encontrado: {fp}")
        urls += [u.strip() for u in fp.read_text().splitlines() if u.strip() and not u.startswith("#")]

    if not urls:
        sys.exit("Sin URLs. Pasa URLs como argumentos o usa --file urls.txt")

    # Verificar yt-dlp
    try:
        subprocess.run([sys.executable, "-m", "yt_dlp", "--version"],
                       capture_output=True, check=True)
    except Exception:
        sys.exit("yt-dlp no instalado. Ejecuta: pip install yt-dlp")

    token = login(args.user, args.password)

    download_dir = Path(tempfile.mkdtemp(prefix="flakai_dl_"))
    print(f"[info] Descargando en: {download_dir}")

    ok, fail = 0, 0

    for url in urls:
        video_path = download_video(url, download_dir)
        if not video_path:
            fail += 1
            continue

        video_id = upload_video(token, video_path)
        if video_id:
            ok += 1
        else:
            fail += 1

        if not args.keep and video_path.exists():
            video_path.unlink()

    print(f"\n[done] ✓ {ok} subidos, ✗ {fail} fallados")
    if not args.keep:
        try:
            download_dir.rmdir()
        except OSError:
            pass


if __name__ == "__main__":
    main()
