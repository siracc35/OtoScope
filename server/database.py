"""
database.py — Database connection and session management.

Responsibility: own the SQLAlchemy engine, the session factory, and a
dependency that hands a fresh session to each request. Nothing about cars or
Gemini lives here — only "how do we talk to the DB".
"""

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

# The SQLite file lives next to this module (server/otoscope.db), regardless of
# the process's working directory. *.db is gitignored, so it never leaves your machine.
DB_PATH = Path(__file__).parent / "otoscope.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

# create_engine = the low-level "connection pool" to the database.
# check_same_thread=False is a SQLite-specific need: by default SQLite forbids
# using one connection across threads, but FastAPI serves requests on a thread
# pool. This flag lifts that restriction (safe here because each request gets
# its own short-lived session).
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# SessionLocal is a FACTORY: calling SessionLocal() creates a new DB session
# (a "conversation" with the DB for one unit of work).
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base is the parent class every ORM table model inherits from. SQLAlchemy
# collects all subclasses of Base to know which tables to create.
Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session and ALWAYS closes it.

    The pattern (open -> yield -> close in finally) guarantees the connection
    is returned to the pool even if the request raises. FastAPI injects the
    yielded session wherever we write `db: Session = Depends(get_db)`.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
