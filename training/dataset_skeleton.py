"""
Esqueleto para cargar el JSONL exportado desde la API (`api.exportLabels` → reviewed clips).

Instalación opcional:
    pip install torch torchvision

Este archivo NO entrena nada: sirve como plantilla para un script real en GPU.
"""
from __future__ import annotations

import json
from pathlib import Path

try:
    from torch.utils.data import Dataset as TorchDataset
except ImportError:
    TorchDataset = object


class ReviewedClipExportDataset(TorchDataset):
    """Una fila por clip revisado (aprobar/rechazar)."""

    def __init__(self, jsonl_path: Path):
        self.rows: list[dict] = []
        with open(jsonl_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    self.rows.append(json.loads(line))

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, idx: int):
        row = self.rows[idx]
        # Sugerencias para el siguiente paso:
        # - Si training_role == "positive": usar event_type como etiqueta de clase.
        # - Si training_role == "negative": binario "no evento" o contrastive loss.
        # - Decodificar solo el clip: Path(row["clip_path"]) con torchvision.io.read_video
        #   o ffmpeg pipe para no cargar el partido entero.
        return row


if __name__ == "__main__":
    print(
        "Uso: ds = ReviewedClipExportDataset(Path('flakai_etiquetas_equipo.jsonl')); "
        f"len(ds) filas"
    )
