"""
Configuración centralizada (12-factor). Usar variables de entorno o archivo `.env` en `backend/`.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Base de datos (SQLite MVP; en producción: postgresql+psycopg://...)
    database_url: str = "sqlite:///./flak_ai.db"

    jwt_secret: str = "flakAI-secret-key-change-in-production-2024"

    # FFmpeg: vacío = buscar en PATH (recomendado en servidores Linux).
    ffmpeg_path: str = ""
    ffprobe_path: str = ""

    # Carpeta local con vídeos brutos para entrenamiento / manifiesto (no se copian al repo).
    dataset_videos_dir: str = r"C:\Users\saamu\Videos\analisisia"

    # Manifiesto generado por scripts/build_dataset_manifest.py (relativo a la raíz del repo).
    dataset_manifest_path: str = "datasets/manifest.jsonl"

    # Detector: solo `mock` incluido; sustituir por onnx/torch servicio externo.
    detector_backend: str = "mock"
    model_version: str = "mock-1.0.0"

    # Duración total del clip centrado en el evento (window/2 antes y window/2 después)
    clip_window_seconds: float = 30.0
    auto_approve_confidence: float = 101.0  # todo va a revisión manual

    # Mock detector: mínimo de eventos (escala automáticamente con la duración del vídeo)
    mock_events_min: int = 5
    mock_events_max: int = 500  # límite de seguridad, raramente alcanzado
    # Mínimo de segundos entre eventos mock (permite eventos consecutivos como córners seguidos)
    mock_min_gap_seconds: float = 20.0

    # Stripe — añadir en .env (no commitear)
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id_pro: str = ""
    stripe_price_id_club: str = ""
    app_url: str = "http://localhost:3000"

    # ── ML / PyTorch detector ────────────────────────────────────────────
    # Stride en segundos entre ventanas de detección (menor = más preciso, más lento)
    torch_detection_stride: float = 5.0
    # Confianza mínima (%) para emitir un evento (0-100)
    torch_detection_threshold: float = 40.0
    # Ventana NMS: suprimir detecciones del mismo tipo dentro de N segundos
    torch_nms_window: float = 20.0
    # Número de frames a extraer por ventana
    torch_n_frames: int = 16


@lru_cache
def get_settings() -> Settings:
    return Settings()


def manifest_path_resolved() -> Path:
    """Ruta absoluta al archivo manifest JSONL."""
    s = get_settings()
    raw = Path(s.dataset_manifest_path)
    if raw.is_absolute():
        return raw
    repo_root = Path(__file__).resolve().parent.parent
    return (repo_root / raw).resolve()
