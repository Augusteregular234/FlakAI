# Etiquetado humano y camino hacia deep learning

## ¿Dónde está el «etiquetado»?

En FlakAI **no hace falta una herramienta aparte**: la pantalla **Revisión** es el etiquetado.

- **Aceptar** un clip = confirmas que, en ese instante del partido, la clase propuesta por el modelo (gol, córner, etc.) es **aceptable** para ese recorte (`training_role: positive` en el export).
- **Rechazar** = ese clip es **negativo** para entrenamiento: falso positivo, clase equivocada o recorte inútil (`training_role: negative`).

Los clips que siguen **pendientes** no se exportan: primero hay que decidir.

## Exportación

Desde **Revisión** (o los endpoints de API) puedes descargar:

| Quién | Endpoint | Contenido |
|-------|----------|-----------|
| Usuario del equipo | `GET /api/export/reviewed?format=jsonl` | Solo clips revisados de su equipo |
| Administrador | `GET /api/admin/export/reviewed?format=jsonl` | Todos los equipos |

Formatos: **JSONL** (una fila JSON por clip, ideal para pipelines) o **CSV** (Excel / pandas).

Campos relevantes: `clip_path`, `video_source_path`, `event_type`, `review_status`, `training_role`, `model_confidence`, `model_version`.

## ¿Por qué no «entrena» la app sola?

Entrenar redes para vídeo de fútbol requiere:

1. **Muchas etiquetas** (miles de eventos balanceados por clase).
2. **GPU** y tiempo (horas/días por experimento).
3. Un **modelo elegido** (clasificación por clip, action spotting en vídeo largo, audio+RGB, etc.).

Lo que sí queda hecho en el proyecto es el **puente**: decisiones humanas → archivo estándar → tu script en Python/PyTorch.

## Referencias serias (benchmarks y líneas de trabajo)

- **SoccerNet**: benchmark amplio para comprensión de vídeo de fútbol, incluye *action spotting* (localizar acciones en tiempo). Paper: [SoccerNet: A Scalable Dataset for Action Spotting in Soccer Videos](https://arxiv.org/abs/1804.04527). Sitio: [soccer-net.org](https://www.soccer-net.org/).
- Repositorio oficial de tareas y código de referencia: [SoccerNet en GitHub](https://github.com/SoccerNet/SoccerNet).
- Tu carpeta de vídeos brutos + **manifest** (`scripts/build_dataset_manifest.py`) sirve para **pretrain / fine-tune** al lado del export de clips revisados.

## Próximo paso técnico recomendado

1. Acumular export JSONL con suficientes **approved** y **rejected** por clase.
2. En un **entorno aparte** (`pip install torch ...`), cargar filas con `training/README.md` y el esqueleto `training/dataset_skeleton.py`.
3. Empezar por un modelo **por clip** (clasificar el MP4 del clip) antes de meter vídeo completo no recortado.
