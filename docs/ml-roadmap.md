# Hoja de ruta ML / precisión de eventos

Objetivo de producto: maximizar acierto en goles, córners, saques de banda y faltas, con confianza bien calibrada.

## 0. Inventario local de vídeos

- Coloca los partidos en la carpeta configurada por `DATASET_VIDEOS_DIR` (por defecto `C:\Users\saamu\Videos\analisisia`).
- Ejecuta desde la raíz del repo: `python scripts/build_dataset_manifest.py` para generar `datasets/manifest.jsonl` (rutas, tamaño, duración vía ffprobe, hash parcial). Ese archivo alimenta pipelines offline sin copiar los vídeos al git.

## 1. Datos y etiquetado

- Dataset por tipo de cámara (Veo, lateral, cenital) y calidades distintas.
- Guías de etiquetado por clase (qué cuenta como falta vs jugada normal).
- Train / validation / test por temporadas o clubes para evitar fugas.

## 2. Modelo

- Baselines: clasificación por clip corto + modelo temporal (video/audio).
- Explorar señales de audio (silbato) fusionadas con visión para faltas.
- Versionado de modelo (`model_version` en API y logs).

## 3. Evaluación

- Métricas por clase (precision / recall), no solo accuracy global.
- Curvas de calibración para que “confianza 90%” signifique ~90% de aciertos en validación.

## 4. Human-in-the-loop

- Exportar clips aceptados/rechazados para reentrenamiento (active learning).
- Priorizar etiquetado de clases con peor F1.

## 5. Infraestructura

- Cola de trabajos (Celery/RQ) en lugar de solo `BackgroundTasks` en producción.
- Almacenamiento de objetos (S3/GCS) y GPU para inferencia si el modelo lo requiere.

Este MVP usa IA simulada; el siguiente paso es registrar predicciones y etiquetas humanas en base de datos para medir de verdad.
