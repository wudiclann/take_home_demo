# SQLite engine/session setup
# SQLite 数据库引擎与会话（session）初始化

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DEFAULT_DATABASE_PATH = DATA_DIR / "app.db"
# APP_DB_PATH lets tests point at an isolated temp file instead of the real dev database.
# APP_DB_PATH 让测试可以指向一个隔离的临时文件，而不是真实的开发数据库。
DATABASE_PATH = Path(os.environ.get("APP_DB_PATH", DEFAULT_DATABASE_PATH))

engine = create_engine(f"sqlite:///{DATABASE_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    """Creates the data directory and any tables that don't exist yet. Safe to
    call repeatedly -- never drops or alters existing tables.
    创建数据目录，以及所有尚不存在的数据表。可以重复调用——
    不会删除或修改已存在的表。"""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)


def get_session() -> Session:
    """Returns a new SQLAlchemy session bound to the app's database.
    返回一个绑定到应用数据库的新 SQLAlchemy 会话。"""
    return SessionLocal()


if __name__ == "__main__":
    # Lets you run `python -m app.db.session` to initialize the DB manually.
    # 允许直接运行 `python -m app.db.session` 来手动初始化数据库。
    init_db()
    print(f"Initialized SQLite database at {DATABASE_PATH}")
