# Import all models here so init_db() picks them up when creating tables.
from app.models.units import Unit, Contact  # noqa: F401
from app.models.meter_readings import MeterReading  # noqa: F401
