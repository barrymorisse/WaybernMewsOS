"""
Database setup for Waybern Mews OS.

This module establishes the SQLite connection and provides the SQLAlchemy
Base class that all future models will inherit from. It also provides
get_db(), a dependency used in FastAPI routes to open and close database
sessions safely.
"""

from sqlalchemy import create_engine, text
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


def _apply_migrations():
    """
    Apply schema changes that SQLAlchemy's create_all won't handle automatically.
    Each statement is wrapped in try/except so it is safe to run on every startup.
    """
    add_columns = [
        ("coj_invoices",     "billing_year",             "INTEGER"),
        ("coj_invoices",     "billing_month",            "INTEGER"),
        ("coj_invoices",     "pdf_path",                 "VARCHAR"),
        ("complex_settings", "electricity_meter_number", "VARCHAR"),
        ("complex_settings", "water_meter_number",       "VARCHAR"),
        # Module 2c — derived consumption and grossed-up figures on meter_readings
        ("meter_readings", "elec_unit_1_consumption",  "NUMERIC(12,4)"),
        ("meter_readings", "elec_unit_2_consumption",  "NUMERIC(12,4)"),
        ("meter_readings", "elec_unit_3_consumption",  "NUMERIC(12,4)"),
        ("meter_readings", "elec_unit_4_consumption",  "NUMERIC(12,4)"),
        ("meter_readings", "elec_unit_5_consumption",  "NUMERIC(12,4)"),
        ("meter_readings", "elec_common_consumption",  "NUMERIC(12,4)"),
        ("meter_readings", "elec_unit_1_grossed_up",   "NUMERIC(12,4)"),
        ("meter_readings", "elec_unit_2_grossed_up",   "NUMERIC(12,4)"),
        ("meter_readings", "elec_unit_3_grossed_up",   "NUMERIC(12,4)"),
        ("meter_readings", "elec_unit_4_grossed_up",   "NUMERIC(12,4)"),
        ("meter_readings", "elec_unit_5_grossed_up",   "NUMERIC(12,4)"),
        ("meter_readings", "elec_common_grossed_up",   "NUMERIC(12,4)"),
        ("meter_readings", "water_unit_1_consumption", "NUMERIC(12,4)"),
        ("meter_readings", "water_unit_2_consumption", "NUMERIC(12,4)"),
        ("meter_readings", "water_unit_3_consumption", "NUMERIC(12,4)"),
        ("meter_readings", "water_unit_4_consumption", "NUMERIC(12,4)"),
        ("meter_readings", "water_unit_5_consumption", "NUMERIC(12,4)"),
        ("meter_readings", "water_common_consumption", "NUMERIC(12,4)"),
        ("meter_readings", "water_unit_1_grossed_up",  "NUMERIC(12,4)"),
        ("meter_readings", "water_unit_2_grossed_up",  "NUMERIC(12,4)"),
        ("meter_readings", "water_unit_3_grossed_up",  "NUMERIC(12,4)"),
        ("meter_readings", "water_unit_4_grossed_up",  "NUMERIC(12,4)"),
        ("meter_readings", "water_unit_5_grossed_up",  "NUMERIC(12,4)"),
        ("meter_readings", "water_common_grossed_up",  "NUMERIC(12,4)"),
        # VAT scaling factors added to billing_calculations
        ("billing_calculations", "elec_vat_factor",  "NUMERIC(10,6)"),
        ("billing_calculations", "water_vat_factor", "NUMERIC(10,6)"),
    ]
    # Rename columns: gross-up → adjustment terminology (2026-05)
    rename_columns = [
        ("meter_readings",        "elec_unit_1_grossed_up",   "elec_unit_1_adjusted"),
        ("meter_readings",        "elec_unit_2_grossed_up",   "elec_unit_2_adjusted"),
        ("meter_readings",        "elec_unit_3_grossed_up",   "elec_unit_3_adjusted"),
        ("meter_readings",        "elec_unit_4_grossed_up",   "elec_unit_4_adjusted"),
        ("meter_readings",        "elec_unit_5_grossed_up",   "elec_unit_5_adjusted"),
        ("meter_readings",        "elec_common_grossed_up",   "elec_common_adjusted"),
        ("meter_readings",        "water_unit_1_grossed_up",  "water_unit_1_adjusted"),
        ("meter_readings",        "water_unit_2_grossed_up",  "water_unit_2_adjusted"),
        ("meter_readings",        "water_unit_3_grossed_up",  "water_unit_3_adjusted"),
        ("meter_readings",        "water_unit_4_grossed_up",  "water_unit_4_adjusted"),
        ("meter_readings",        "water_unit_5_grossed_up",  "water_unit_5_adjusted"),
        ("meter_readings",        "water_common_grossed_up",  "water_common_adjusted"),
        ("billing_calculations",  "elec_gross_up_factor",     "elec_adjustment_factor"),
        ("billing_calculations",  "water_gross_up_factor",    "water_adjustment_factor"),
        ("billing_step_allocations", "grossed_up_usage",      "adjusted_usage"),
    ]
    drop_columns = [
        ("coj_invoices", "meter_number"),
    ]
    with engine.connect() as conn:
        for table, column, typedef in add_columns:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {typedef}"))
                conn.commit()
            except Exception:
                pass  # Column already exists
        for table, old_col, new_col in rename_columns:
            try:
                conn.execute(text(f"ALTER TABLE {table} RENAME COLUMN {old_col} TO {new_col}"))
                conn.commit()
            except Exception:
                pass  # Already renamed or column doesn't exist
        for table, column in drop_columns:
            try:
                conn.execute(text(f"ALTER TABLE {table} DROP COLUMN {column}"))
                conn.commit()
            except Exception:
                pass  # Column already removed or never existed


def init_db():
    """
    Creates all database tables defined by models that have imported Base.
    Called once on application startup. Safe to call multiple times —
    SQLAlchemy only creates tables that don't already exist.
    """
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _apply_migrations()
