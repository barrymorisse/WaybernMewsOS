"""
Service layer for Module 1: Units & Owners Registry.

All database queries and write operations for units and contacts live here.
Routes call these functions rather than querying the database directly,
keeping route handlers thin and logic easy to find.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.units import Unit, Contact


def get_all_units(db: Session) -> list[Unit]:
    """Return all units ordered by unit number."""
    return db.query(Unit).order_by(Unit.unit_number).all()


def get_unit(db: Session, unit_id: int) -> Unit:
    """Return a single unit by ID, or raise a 404 if not found."""
    unit = db.query(Unit).filter(Unit.id == unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    return unit


def update_unit(db: Session, unit_id: int, description: str | None, participation_quota: float) -> Unit:
    """Update editable fields on a unit. Unit number is not editable."""
    unit = get_unit(db, unit_id)
    unit.description = description
    unit.participation_quota = participation_quota
    db.commit()
    db.refresh(unit)
    return unit


def get_contact(db: Session, contact_id: int) -> Contact:
    """Return a single contact by ID, or raise a 404 if not found."""
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


def create_contact(
    db: Session,
    unit_id: int,
    name: str,
    phone: str | None,
    email: str | None,
    is_owner: bool,
    is_tenant: bool,
    is_resident: bool,
    is_trustee: bool,
) -> Contact:
    """Create a new contact for a unit."""
    # Verify the unit exists before creating the contact
    get_unit(db, unit_id)

    contact = Contact(
        unit_id=unit_id,
        name=name,
        phone=phone or None,
        email=email or None,
        is_owner=is_owner,
        is_tenant=is_tenant,
        is_resident=is_resident,
        is_trustee=is_trustee,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def update_contact(
    db: Session,
    contact_id: int,
    name: str,
    phone: str | None,
    email: str | None,
    is_owner: bool,
    is_tenant: bool,
    is_resident: bool,
    is_trustee: bool,
) -> Contact:
    """Update all fields on an existing contact."""
    contact = get_contact(db, contact_id)
    contact.name = name
    contact.phone = phone or None
    contact.email = email or None
    contact.is_owner = is_owner
    contact.is_tenant = is_tenant
    contact.is_resident = is_resident
    contact.is_trustee = is_trustee
    db.commit()
    db.refresh(contact)
    return contact


def delete_contact(db: Session, contact_id: int) -> None:
    """Delete a contact permanently."""
    contact = get_contact(db, contact_id)
    db.delete(contact)
    db.commit()
