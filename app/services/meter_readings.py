"""
Service layer for Module 2a: Meter Readings.

All database queries and write operations for meter readings live here.
Routes call these functions rather than querying the database directly.
"""

import calendar
from datetime import date
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.meter_readings import MeterReading


def get_all_readings(db: Session) -> list[MeterReading]:
    """Return all readings ordered newest first."""
    return (
        db.query(MeterReading)
        .order_by(MeterReading.year.desc(), MeterReading.month.desc())
        .all()
    )


def get_reading(db: Session, reading_id: int) -> MeterReading:
    """Return a single reading by ID, or raise 404 if not found."""
    reading = db.query(MeterReading).filter(MeterReading.id == reading_id).first()
    if not reading:
        raise HTTPException(status_code=404, detail="Reading not found")
    return reading


def get_reading_for_month(db: Session, year: int, month: int) -> MeterReading | None:
    """Return the reading for a specific month, or None if it doesn't exist."""
    return (
        db.query(MeterReading)
        .filter(MeterReading.year == year, MeterReading.month == month)
        .first()
    )


def _parse_float(value: str | None) -> float | None:
    """Convert a form string value to float, returning None if blank."""
    if value is None or value.strip() == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _last_day_of_month(year: int, month: int) -> date:
    """Return the last calendar date of the given month."""
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, last_day)


def create_reading(db: Session, data: dict) -> MeterReading:
    """
    Insert a new monthly reading. Raises 400 if a reading for that
    month already exists.
    """
    year = int(data["year"])
    month = int(data["month"])

    # Duplicate check before attempting insert
    if get_reading_for_month(db, year, month):
        raise HTTPException(
            status_code=400,
            detail=f"A reading for {calendar.month_name[month]} {year} already exists."
        )

    reading = MeterReading(
        year=year,
        month=month,
        reading_date=date.fromisoformat(data["reading_date"]),
        elec_unit_1=_parse_float(data.get("elec_unit_1")),
        elec_unit_2=_parse_float(data.get("elec_unit_2")),
        elec_unit_3=_parse_float(data.get("elec_unit_3")),
        elec_unit_4=_parse_float(data.get("elec_unit_4")),
        elec_unit_5=_parse_float(data.get("elec_unit_5")),
        elec_public_lighting=_parse_float(data.get("elec_public_lighting")),
        elec_total=_parse_float(data.get("elec_total")),
        water_unit_1=_parse_float(data.get("water_unit_1")),
        water_unit_2=_parse_float(data.get("water_unit_2")),
        water_unit_3=_parse_float(data.get("water_unit_3")),
        water_unit_4=_parse_float(data.get("water_unit_4")),
        water_unit_5=_parse_float(data.get("water_unit_5")),
        water_total=_parse_float(data.get("water_total")),
    )
    db.add(reading)
    db.commit()
    db.refresh(reading)
    return reading


def update_reading(db: Session, reading_id: int, data: dict) -> MeterReading:
    """Update all fields on an existing reading."""
    reading = get_reading(db, reading_id)
    reading.reading_date = date.fromisoformat(data["reading_date"])
    reading.elec_unit_1 = _parse_float(data.get("elec_unit_1"))
    reading.elec_unit_2 = _parse_float(data.get("elec_unit_2"))
    reading.elec_unit_3 = _parse_float(data.get("elec_unit_3"))
    reading.elec_unit_4 = _parse_float(data.get("elec_unit_4"))
    reading.elec_unit_5 = _parse_float(data.get("elec_unit_5"))
    reading.elec_public_lighting = _parse_float(data.get("elec_public_lighting"))
    reading.elec_total = _parse_float(data.get("elec_total"))
    reading.water_unit_1 = _parse_float(data.get("water_unit_1"))
    reading.water_unit_2 = _parse_float(data.get("water_unit_2"))
    reading.water_unit_3 = _parse_float(data.get("water_unit_3"))
    reading.water_unit_4 = _parse_float(data.get("water_unit_4"))
    reading.water_unit_5 = _parse_float(data.get("water_unit_5"))
    reading.water_total = _parse_float(data.get("water_total"))
    db.commit()
    db.refresh(reading)
    return reading
