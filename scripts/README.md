# Scripts auxiliares

## `build_dataset_manifest.py`

Lee `DATASET_VIDEOS_DIR` desde la configuración del backend (`backend/.env`), lista vídeos conocidos y escribe `datasets/manifest.jsonl` con duración (ffprobe) y metadatos ligeros.

```powershell
cd F:\IA\Analisis IA-v2
python scripts/build_dataset_manifest.py
```

Requiere `ffprobe` en PATH o variables `FFPROBE_PATH` / `FFMPEG_PATH` en `backend/.env`.
