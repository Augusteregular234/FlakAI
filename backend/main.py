from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine
import models
from routers import auth, videos, clips

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="FlakAI v2 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(videos.router)
app.include_router(clips.router)


@app.get("/health")
def health():
    return {"status": "ok", "app": "FlakAI v2"}
