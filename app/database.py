"""
Database setup for Waybern Mews OS.

This module establishes the SQLite connection and provides the SQLAlchemy
Base class that all future models will inherit from. It also provides
get_db(), a dependency used in FastAPI routes to open and close database
sessions safely.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Resolve the path to the database file relative to this file's location.
# This means the app works regardless of where it is launched from.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'data', 'waybern.db')}"

# connect_args is required for SQLite to allow use across threads (FastAPI uses threads).
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

# SessionLocal is a factory: calling SessionLocal() creates a new database session.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base is the parent class for all ORM models in this project.
Base = declarative_base()


def get_db():
    """
    FastAPI dependency that opens a database session for a request and
    closes it when the request is complete, even if an error occurs.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Creates all database tables defined by models that have imported Base.
    Called once on application startup. Safe to call multiple times —
    SQLAlchemy only creates tables that don't already exist.
    """
    # Import models here so SQLAlchemy knows about them before calling create_all.
    # As new modules are added, import their models here.
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
