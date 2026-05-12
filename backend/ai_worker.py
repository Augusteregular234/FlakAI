import asyncio
import random
import subprocess
import os
from datetime import datetime
from sqlalchemy.orm import Session
import models
from database import SessionLocal

FFMPEG_PATH = r"C:\Users\saamu\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"
CLIPS_DIR = os.path.join(os.path.dirname(__file__), "clips")

EVENT_TYPES = [
    models.EventType.goal,
    models.EventType.corner,
    models.EventType.throw_in,
    models.EventType.foul,
]

EVENT_LABELS = {
    "goal": "Gol",
    "corner": "Córner",
    "throw_in": "Saque de Banda",
    "foul": "Falta",
}


def simulate_ai_detection(video_path: str) -> list[dict]:
    num_events = random.randint(3, 5)
    events = []
    used_timestamps = []

    for _ in range(num_events):
        timestamp = random.uniform(35, 300)
        while any(abs(timestamp - t) < 35 for t in used_timestamps):
            timestamp = random.uniform(35, 300)
        used_timestamps.append(timestamp)

        events.append({
            "event_type": random.choice(EVENT_TYPES),
            "timestamp_seconds": round(timestamp, 2),
            "confidence": round(random.uniform(50, 99), 1),
        })

    return sorted(events, key=lambda e: e["timestamp_seconds"])


def generate_clip(video_path: str, event_timestamp: float, clip_filename: str) -> str | None:
    os.makedirs(CLIPS_DIR, exist_ok=True)
    clip_path = os.path.join(CLIPS_DIR, clip_filename)

    start = max(0, event_timestamp - 30)
    duration = 30

    if not os.path.exists(FFMPEG_PATH):
        _create_dummy_clip(clip_path)
        return clip_path

    if not os.path.exists(video_path):
        _create_dummy_clip(clip_path)
        return clip_path

    cmd = [
        FFMPEG_PATH,
        "-y",
        "-ss", str(start),
        "-i", video_path,
        "-t", str(duration),
        "-c:v", "libx264",
        "-c:a", "aac",
        "-movflags", "+faststart",
        clip_path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode == 0 and os.path.exists(clip_path):
            return clip_path
    except Exception:
        pass

    _create_dummy_clip(clip_path)
    return clip_path


def _create_dummy_clip(clip_path: str):
    if not os.path.exists(FFMPEG_PATH):
        with open(clip_path, "wb") as f:
            f.write(b"\x00" * 1024)
        return

    cmd = [
        FFMPEG_PATH,
        "-y",
        "-f", "lavfi",
        "-i", "color=c=black:s=1280x720:r=25:d=5",
        "-f", "lavfi",
        "-i", "anullsrc=r=44100:cl=stereo",
        "-t", "5",
        "-c:v", "libx264",
        "-c:a", "aac",
        clip_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=30)
    except Exception:
        with open(clip_path, "wb") as f:
            f.write(b"\x00" * 1024)


async def process_video(video_id: int):
    await asyncio.sleep(3)

    db: Session = SessionLocal()
    try:
        video = db.query(models.VideoMatch).filter(models.VideoMatch.id == video_id).first()
        if not video:
            return

        video.status = models.VideoStatus.processing
        db.commit()

        await asyncio.sleep(7)

        events = simulate_ai_detection(video.file_path)

        for event_data in events:
            clip_filename = f"clip_{video_id}_{int(event_data['timestamp_seconds'])}_{event_data['event_type'].value}.mp4"
            clip_path = generate_clip(video.file_path, event_data["timestamp_seconds"], clip_filename)

            review_status = (
                models.ReviewStatus.approved
                if event_data["confidence"] >= 80
                else models.ReviewStatus.pending
            )

            clip = models.EventClip(
                video_id=video.id,
                team_id=video.team_id,
                event_type=event_data["event_type"],
                timestamp_seconds=event_data["timestamp_seconds"],
                confidence=event_data["confidence"],
                clip_path=clip_path,
                clip_filename=clip_filename,
                review_status=review_status,
            )
            db.add(clip)

        video.status = models.VideoStatus.completed
        video.processed_at = datetime.utcnow()
        db.commit()

    except Exception as e:
        video = db.query(models.VideoMatch).filter(models.VideoMatch.id == video_id).first()
        if video:
            video.status = models.VideoStatus.error
            db.commit()
    finally:
        db.close()
