"""
Watches analisisFLK folder for new mp4 files and auto-queues them for processing.
Runs until all 3 highlight videos are ingested.
"""
import sys, time, requests
sys.path.insert(0, ".")
from pathlib import Path

FOLDER = Path(r"C:\Users\saamu\Videos\analisisFLK")
BASE   = "http://localhost:8000"
TARGET_TITLES = ["Best Goals of the Year 2025", "Best Goals of the Year 2026", "Best Goals of the Season"]

def login():
    r = requests.post(f"{BASE}/api/auth/login", json={"username":"admin","password":"admin"})
    return r.json()["access_token"]

def get_existing():
    from database import SessionLocal
    import models as m
    db = SessionLocal()
    names = {v.original_name for v in db.query(m.VideoMatch).all()}
    db.close()
    return names

def ingest(path, token):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.post(f"{BASE}/api/admin/videos/ingest", json=[str(path)], headers=headers)
    return r.json()

ingested = set()
print("Watching for new highlight videos...")

while True:
    try:
        token = login()
        existing = get_existing()

        for f in FOLDER.glob("*.mp4"):
            if f.name in existing or f.name in ingested:
                continue
            # Check if it's one of our highlight downloads
            is_highlight = any(t.lower() in f.name.lower() for t in TARGET_TITLES)
            if not is_highlight:
                continue
            # Check file is not still being written (size stable)
            s1 = f.stat().st_size
            time.sleep(3)
            s2 = f.stat().st_size
            if s1 != s2:
                print(f"Still downloading: {f.name}")
                continue

            print(f"Ingesting: {f.name}")
            result = ingest(f, token)
            print(f"  -> {result}")
            ingested.add(f.name)

        if len(ingested) >= 3:
            print("All 3 highlight videos ingested and queued!")
            # Trigger processing
            headers = {"Authorization": f"Bearer {token}"}
            r = requests.post(f"{BASE}/api/admin/videos/trigger-queued", headers=headers)
            print(f"Processing triggered: {r.json()}")
            break

    except Exception as e:
        print(f"Error: {e}")

    time.sleep(15)

print("Done.")
