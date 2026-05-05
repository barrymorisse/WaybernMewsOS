"""
Database model for Module 2a: Meter Readings.

One row per calendar month. Stores the cumulative meter readings for all 13
meters at Waybern Mews — 7 electricity and 6 water. Values are nullable so
that partial readings (e.g. one meter inaccessible) can still be saved.

Consumption for a given month is derived by subtracting the prior month's
reading at query time — it is never stored here.
"""

from sqlalchemy import Column, Integer, Float, Date, UniqueConstraint, Numeric
from app.database import Base


class MeterReading(Base):
    __tablename__ = "meter_readings"

    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)   # 1 = January, 12 = December
    reading_date = Column(Date, nullable=False)  # Actual date Barry took the readings

    # Electricity readings (kWh) — cumulative meter values
    elec_unit_1 = Column(Float, nullable=True)
    elec_unit_2 = Column(Float, nullable=True)
    elec_unit_3 = Column(Float, nullable=True)
    elec_unit_4 = Column(Float, nullable=True)
    elec_unit_5 = Column(Float, nullable=True)
    elec_public_lighting = Column(Float, nullable=True)
    elec_total = Column(Float, nullable=True)

    # Water readings (kL) — cumulative meter values
    water_unit_1 = Column(Float, nullable=True)
    water_unit_2 = Column(Float, nullable=True)
    water_unit_3 = Column(Float, nullable=True)
    water_unit_4 = Column(Float, nullable=True)
    water_unit_5 = Column(Float, nullable=True)
    water_total = Column(Float, nullable=True)

    # --- Derived columns populated by Module 2c billing calculation ---
    # Consumption = this month's reading minus previous month's reading.
    # These are written when a billing calculation runs and cleared on recalculate.

    # Raw consumption per unit and common property (current − previous reading)
    elec_unit_1_consumption = Column(Numeric(12, 4), nullable=True)
    elec_unit_2_consumption = Column(Numeric(12, 4), nullable=True)
    elec_unit_3_consumption = Column(Numeric(12, 4), nullable=True)
    elec_unit_4_consumption = Column(Numeric(12, 4), nullable=True)
    elec_unit_5_consumption = Column(Numeric(12, 4), nullable=True)
    elec_common_consumption  = Column(Numeric(12, 4), nullable=True)  # max(0, total − sum of units)

    water_unit_1_consumption = Column(Numeric(12, 4), nullable=True)
    water_unit_2_consumption = Column(Numeric(12, 4), nullable=True)
    water_unit_3_consumption = Column(Numeric(12, 4), nullable=True)
    water_unit_4_consumption = Column(Numeric(12, 4), nullable=True)
    water_unit_5_consumption = Column(Numeric(12, 4), nullable=True)
    water_common_consumption  = Column(Numeric(12, 4), nullable=True)

    # Adjusted consumption (raw × CoJ adjustment factor) — aligns our readings to CoJ totals
    elec_unit_1_adjusted = Column(Numeric(12, 4), nullable=True)
    elec_unit_2_adjusted = Column(Numeric(12, 4), nullable=True)
    elec_unit_3_adjusted = Column(Numeric(12, 4), nullable=True)
    elec_unit_4_adjusted = Column(Numeric(12, 4), nullable=True)
    elec_unit_5_adjusted = Column(Numeric(12, 4), nullable=True)
    elec_common_adjusted  = Column(Numeric(12, 4), nullable=True)

    water_unit_1_adjusted = Column(Numeric(12, 4), nullable=True)
    water_unit_2_adjusted = Column(Numeric(12, 4), nullable=True)
    water_unit_3_adjusted = Column(Numeric(12, 4), nullable=True)
    water_unit_4_adjusted = Column(Numeric(12, 4), nullable=True)
    water_unit_5_adjusted = Column(Numeric(12, 4), nullable=True)
    water_common_adjusted  = Column(Numeric(12, 4), nullable=True)

    # Enforce one reading set per calendar month
    __table_args__ = (
        UniqueConstraint("year", "month", name="uq_meter_readings_year_month"),
    )
