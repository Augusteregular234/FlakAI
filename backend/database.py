from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import get_settings

SQLALCHEMY_DATABASE_URL = get_settings().database_url

_engine_kwargs = {}
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(SQLALCHEMY_DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def _migrate_users(conn_engine) -> None:
    insp = inspect(conn_engine)
    if "users" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    if "is_admin" not in cols:
        with conn_engine.begin() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0"))


def _migrate_teams(conn_engine) -> None:
    insp = inspect(conn_engine)
    if "teams" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("teams")}
    with conn_engine.begin() as conn:
        if "status" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE teams ADD COLUMN status VARCHAR(32) DEFAULT 'active'"
                )
            )
        if "requested_at" not in cols:
            conn.execute(text("ALTER TABLE teams ADD COLUMN requested_at DATETIME"))
        if "approved_at" not in cols:
            conn.execute(text("ALTER TABLE teams ADD COLUMN approved_at DATETIME"))
        if "approved_by_user_id" not in cols:
            conn.execute(
                text("ALTER TABLE teams ADD COLUMN approved_by_user_id INTEGER")
            )
        if "trial_video_used" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE teams ADD COLUMN trial_video_used BOOLEAN DEFAULT 0"
                )
            )
        if "subscription_tier" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE teams ADD COLUMN subscription_tier VARCHAR(32) DEFAULT 'free_trial'"
                )
            )
        if "stripe_customer_id" not in cols:
            conn.execute(
                text("ALTER TABLE teams ADD COLUMN stripe_customer_id VARCHAR(255)")
            )


def _migrate_videos_and_clips(conn_engine) -> None:
    insp = inspect(conn_engine)
    if "videos" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("videos")}
        with conn_engine.begin() as conn:
            if "duration_seconds" not in cols:
                conn.execute(text("ALTER TABLE videos ADD COLUMN duration_seconds REAL"))
            if "processing_started_at" not in cols:
                conn.execute(text("ALTER TABLE videos ADD COLUMN processing_started_at DATETIME"))
            if "processing_events_done" not in cols:
                conn.execute(text("ALTER TABLE videos ADD COLUMN processing_events_done INTEGER DEFAULT 0"))
            if "processing_events_total" not in cols:
                conn.execute(text("ALTER TABLE videos ADD COLUMN processing_events_total INTEGER DEFAULT 0"))
    if "event_clips" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("event_clips")}
        with conn_engine.begin() as conn:
            if "model_version" not in cols:
                conn.execute(
                    text(
                        "ALTER TABLE event_clips ADD COLUMN model_version VARCHAR(64)"
                    )
                )
            if "detector_metadata" not in cols:
                conn.execute(
                    text("ALTER TABLE event_clips ADD COLUMN detector_metadata TEXT")
                )


def run_sqlite_migrations(conn_engine) -> None:
    """Añade columnas nuevas en BD SQLite existentes sin Alembic (MVP)."""
    if "sqlite" not in str(conn_engine.url):
        return
    try:
        _migrate_users(conn_engine)
        _migrate_teams(conn_engine)
        _migrate_videos_and_clips(conn_engine)
    except Exception:
        pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
