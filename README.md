# FlakAI v2 — Análisis Táctico de Fútbol

Plataforma SaaS MVP para análisis automático de partidos de fútbol con IA.

## Stack
- **Frontend**: Next.js 15 · Tailwind CSS · Shadcn/UI · Zustand
- **Backend**: Python FastAPI · SQLAlchemy · SQLite
- **IA**: Mock engine (simula detección de Goles, Córners, Saques, Faltas)
- **Video**: FFmpeg (clips de 30s por evento)

Ruta local de ejemplo: `F:\IA\Analisis IA-v2` (ajusta según tu equipo).

## Inicio rápido

```powershell
# Instalar dependencias nuevas (slowapi, email-validator, …)
cd backend
.\venv\Scripts\pip.exe install -r requirements.txt

# Windows — lanza backend + frontend (desde la raíz del repo)
.\start.ps1
```

### Variables de entorno (backend)

| Variable | Descripción |
|----------|----------------|
| `JWT_SECRET` | Clave para firmar JWT (obligatorio en producción). Por defecto hay un valor solo para desarrollo. |
| `CORS_ORIGINS` | Orígenes extra separados por comas (opcional). Siempre se permiten `localhost` y `127.0.0.1` en el puerto 3000. |

### Usuario administrador (seed)

```powershell
cd backend
.\venv\Scripts\python.exe seed_admin.py
```

Credenciales: **admin** / **admin** (cambiar en producción). El equipo «Administración» queda **activo** y en plan **premium** para pruebas sin límite de subidas.

### Modelo de negocio (MVP)

- **Registro**: cada equipo nuevo queda en estado **pendiente de aprobación** hasta que un admin lo apruebe en **Admin · Equipos** (`/dashboard/admin`).
- **Rechazo**: el nombre del equipo se renombra internamente para liberar el nombre visible para otro registro.
- **Cuota**: un **vídeo de prueba** por equipo en plan `free_trial`; después hace falta **premium** (stub hasta integrar Stripe u otro PSP). Ver `backend/billing/subscription.py`.

### Si el registro muestra “Failed to fetch”

1. Comprueba que el backend está en marcha: http://localhost:8000/docs  
2. Usa la misma forma de URL en el navegador que en CORS: `localhost` y `127.0.0.1` ya están permitidos.  
3. Verifica `frontend/.env.local` → `NEXT_PUBLIC_API_URL=http://localhost:8000`

Manual:
```bash
cd backend && venv\Scripts\python run.py
cd frontend && npm run dev
```

URLs:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Etiquetado humano y export para ML

- **Etiquetado** = pantalla **Revisión**: cada **Aceptar** / **Rechazar** es una etiqueta (`positive` / `negative` en el export).
- **Descarga**: en **Revisión** usa **Etiquetas JSONL / CSV** (equipo). Admin puede **JSONL global**.
- API: `GET /api/export/reviewed?format=jsonl` (equipo), `GET /api/admin/export/reviewed?format=jsonl` (todos).
- Guía y referencias (SoccerNet, etc.): `docs/labeling-and-training.md`. Esqueleto PyTorch: `training/`.

## IA, dataset y escalado

- **Configuración**: copia `backend/.env.example` a `backend/.env` y ajusta rutas (`DATASET_VIDEOS_DIR`, `FFMPEG_PATH`, `JWT_SECRET`, etc.).
- **Detector**: capa `backend/detection/` con contrato estable (`RawEvent`). Por defecto `DETECTOR_BACKEND=mock`; sustituir por ONNX/Torch o API sin cambiar el worker.
- **Clips**: ventana configurable `CLIP_WINDOW_SECONDS`, umbral `AUTO_APPROVE_CONFIDENCE`; FFmpeg resuelto por PATH o `FFMPEG_PATH`.
- **Procesamiento**: `ai_worker` graba `duration_seconds` del vídeo (ffprobe), `model_version` y metadatos JSON por evento para trazabilidad y futuro entrenamiento.
- **Dataset offline**: vídeos en `DATASET_VIDEOS_DIR` → `python scripts/build_dataset_manifest.py` → `datasets/manifest.jsonl`.
- **Admin**: en «Admin · Equipos» verás un bloque **Dataset · ML** con recuento de ficheros y estado del manifest.
- **Gran escala**: ver `docs/scaling.md` (PostgreSQL, colas, object storage, GPU workers).

## Funcionalidades MVP
- Multi-tenant (equipos) con JWT; límites en login/registro (slowapi)
- Aprobación de equipos por administrador
- Subida de vídeos por fragmentos (chunked upload)
- Cuota de 1 vídeo de prueba por equipo (salvo premium)
- Pipeline IA mock: 3-5 eventos por vídeo, 50-99% confianza
- Auto-aprobación si confianza ≥ 80%, revisión manual si < 80%
- Human-in-the-loop: Accept/Reject con teclado (A/R/←/→)
- Dashboard de resultados con filtros por tipo de evento
- Roadmap ML: `docs/ml-roadmap.md`
