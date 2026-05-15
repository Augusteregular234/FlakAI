import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from database import engine, run_sqlite_migrations
import models
from rate_limit import limiter
from config import get_settings
from routers import admin, auth, batches, billing, clips, export_reviewed, ml_admin, videos

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s %(message)s",
)

models.Base.metadata.create_all(bind=engine)
run_sqlite_migrations(engine)

_default_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
_extra = os.getenv("CORS_ORIGINS", "").strip()
_extra_list = [o.strip() for o in _extra.split(",") if o.strip()]
cors_origins = list(dict.fromkeys(_default_origins + _extra_list))

app = FastAPI(title="FlakAI v2 API", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(ml_admin.router)
app.include_router(export_reviewed.router_team)
app.include_router(export_reviewed.router_admin)
app.include_router(videos.router)
app.include_router(clips.router)
app.include_router(batches.router)
app.include_router(billing.router)


@app.get("/health")
def health():
    s = get_settings()
    return {
        "status": "ok",
        "app": "FlakAI v2",
        "detector_backend": s.detector_backend,
        "model_version": s.model_version,
    }
