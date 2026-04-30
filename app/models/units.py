"""
Database models for Module 1: Units & Owners Registry.

Two models:
- Unit: one row per sectional title unit at Waybern Mews (5 total)
- Contact: one row per person associated with a unit (owner, tenant, resident, trustee)

A person can hold multiple roles simultaneously — role flags are independent booleans.
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Unit(Base):
    __tablename__ = "units"

    id = Column(Integer, primary_key=True, index=True)
    unit_number = Column(String, unique=True, nullable=False)  # e.g. "1", "2"
    description = Column(String, nullable=True)
    participation_quota = Column(Float, nullable=False)  # e.g. 0.20 for 20%

    # All people associated with this unit
    contacts = relationship("Contact", back_populates="unit", cascade="all, delete-orphan")


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)

    # Role flags — multiple can be true simultaneously
    is_owner = Column(Boolean, default=False, nullable=False)
    is_tenant = Column(Boolean, default=False, nullable=False)
    is_resident = Column(Boolean, default=False, nullable=False)
    is_trustee = Column(Boolean, default=False, nullable=False)

    unit = relationship("Unit", back_populates="contacts")
