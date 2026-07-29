# SQLite engine/session setup

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DEFAULT_DATABASE_PATH = DATA_DIR / "app.db"
# APP_DB_PATH lets tests point at an isolated temp file instead of the real dev database.
DATABASE_PATH = Path(os.environ.get("APP_DB_PATH", DEFAULT_DATABASE_PATH))

engine = create_engine(f"sqlite:///{DATABASE_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)


def get_session() -> Session:
    return SessionLocal()


if __name__ == "__main__":
    init_db()
    print(f"Initialized SQLite database at {DATABASE_PATH}")
