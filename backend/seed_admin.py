"""
Crea o actualiza el usuario administrador (admin / admin).
Ejecutar desde la carpeta backend:
  venv\\Scripts\\python seed_admin.py
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import SessionLocal, engine, run_sqlite_migrations  # noqa: E402
import models  # noqa: E402
from auth import hash_password  # noqa: E402


def main() -> None:
    models.Base.metadata.create_all(bind=engine)
    run_sqlite_migrations(engine)

    db = SessionLocal()
    try:
        admin = db.query(models.User).filter(models.User.username == "admin").first()
        team = db.query(models.Team).filter(models.Team.name == "Administración").first()
        if not team:
            team = models.Team(
                name="Administración",
                status=models.TeamStatus.active,
                subscription_tier="premium",
                trial_video_used=True,
                approved_at=datetime.utcnow(),
            )
            db.add(team)
            db.flush()
        else:
            team.status = models.TeamStatus.active
            team.subscription_tier = "premium"
            team.trial_video_used = True
            if team.approved_at is None:
                team.approved_at = datetime.utcnow()

        if admin:
            admin.hashed_password = hash_password("admin")
            admin.is_admin = True
            admin.team_id = team.id
            db.commit()
            print("OK: usuario 'admin' actualizado (contraseña: admin).")
            return

        user = models.User(
            username="admin",
            email="admin@local.dev",
            hashed_password=hash_password("admin"),
            team_id=team.id,
            is_admin=True,
        )
        db.add(user)
        db.commit()
        print("OK: usuario admin creado — usuario: admin | contraseña: admin")
    finally:
        db.close()


if __name__ == "__main__":
    main()
