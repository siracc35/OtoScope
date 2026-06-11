"""
database.py — Database connection and session management.

Production: DATABASE_URL env var (Railway PostgreSQL).
Local dev:  falls back to SQLite if DATABASE_URL is not set.
"""

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

_SQLITE_FALLBACK = f"sqlite:///{Path(__file__).parent / 'otoscope.db'}"
DATABASE_URL = os.getenv("DATABASE_URL", _SQLITE_FALLBACK)

# Railway sometimes returns postgres:// — SQLAlchemy requires postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# check_same_thread is SQLite-only; PostgreSQL doesn't accept it
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
