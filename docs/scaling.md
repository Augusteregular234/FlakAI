# Arquitectura a gran escala — FlakAI

Este documento describe cómo evolucionar el MVP (SQLite, BackgroundTasks, mock IA) hacia un servicio robusto y escalable.

## 1. Datos y almacenamiento

| MVP | Producción |
|-----|------------|
| SQLite local | **PostgreSQL** (o Aurora / Cloud SQL): multi-worker, backups, índices |
| Vídeos en disco `./uploads` | **Object storage** (S3, GCS, Azure Blob) + URLs firmadas; nunca Path locals en workers remotos |
| Sin CDN | CDN para clips derivados y streaming segmentado (HLS) si hace falta |

Migración: usar Alembic para esquema; variable `DATABASE_URL` ya está preparada en `config.py`.

## 2. Procesamiento de vídeo e IA

| MVP | Producción |
|-----|------------|
| `BackgroundTasks` en el proceso API | **Cola de trabajos**: Celery + Redis/RabbitMQ, o AWS SQS + workers ECS/Kubernetes |
| Mock detector | Servicio **GPU** (inferencia ONNX/Torch) o API dedicada; mismo contrato `RawEvent` en `detection/` |
| Un proceso uvicorn | API stateless + **N workers** de inferencia autoescalados |

Patrón recomendado: encolar `video_id` tras `complete_upload`; worker ejecuta `process_video` con bloqueo idempotente (`processing_lock` en BD o Redis).

## 3. Observabilidad

- Logging estructurado (JSON) y correlación `video_id` / `trace_id`.
- Métricas: latencia por etapa (upload, probe, inferencia, ffmpeg clip).
- Trazas: OpenTelemetry hacia Datadog / Grafana Cloud.

## 4. Dataset y ML

- Los vídeos en `DATASET_VIDEOS_DIR` no deben copiarse al repositorio Git.
- `scripts/build_dataset_manifest.py` genera `datasets/manifest.jsonl` con rutas y duraciones para pipelines offline.
- Siguiente paso: etiquetado (CVAT, Label Studio), export a formato COCO/YOLO según el modelo, y entrenamiento en máquina con GPU aparte del API.

## 5. Seguridad y multi-tenant

- JWT con rotación y secretos en vault (AWS Secrets Manager, etc.).
- Cuotas por equipo ya preparadas (`trial_video_used`, `subscription_tier`); integrar Stripe y webhooks de pago.
- Límite de tamaño de subida y antivirus opcional en bucket.

## 6. Frontend / API

- Misma API detrás de balanceador; CORS restringido a dominios de producción (`CORS_ORIGINS`).
- Rate limiting ya aplicado en auth; extender a uploads por API key o por equipo.
