# Entrenamiento (fuera del servidor API)

El backend **no entrena modelos** en producción: solo sirve inferencia mock/real y exporta etiquetas.

## Preparación

1. Exporta desde la app **JSONL** de clips revisados (`/dashboard/review` → Etiquetas JSONL).
2. Opcional: instala PyTorch en un virtualenv **dedicado** (no mezclar con `backend/venv` si quieres mantener el API ligero):

```powershell
python -m venv .venv-train
.\.venv-train\Scripts\pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
```

(El índice CUDA depende de tu GPU; en CPU omite `--index-url`.)

## Esqueleto

Ver `dataset_skeleton.py`: lee el JSONL y define un `Dataset` mínimo. Sustituye el `__getitem__` por lectura real de vídeo (por ejemplo recorte temporal desde `video_source_path` o archivo del clip).

## Datos públicos de referencia

Para comparar métricas y arquitecturas, conviene estudiar benchmarks como **SoccerNet** (ver `docs/labeling-and-training.md`).
