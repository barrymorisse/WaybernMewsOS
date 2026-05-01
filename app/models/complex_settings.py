from sqlalchemy import Column, Integer, String
from app.database import Base


class ComplexSettings(Base):
    __tablename__ = "complex_settings"

    id = Column(Integer, primary_key=True, default=1)
    electricity_account_number = Column(String, nullable=True)
    electricity_meter_number = Column(String, nullable=True)
    water_account_number = Column(String, nullable=True)
    water_meter_number = Column(String, nullable=True)
