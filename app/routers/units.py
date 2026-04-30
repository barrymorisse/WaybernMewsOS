"""
Routes for Module 1: Units & Owners Registry.

All pages and form submissions for viewing and editing units and contacts.
Each route either renders a template (GET) or processes a form and redirects (POST).
"""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os

from app.database import get_db
from app.services import units as unit_service

router = APIRouter(prefix="/units", tags=["units"])

templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
)


@router.get("", response_class=HTMLResponse)
async def units_list(request: Request, db: Session = Depends(get_db)):
    """Display all 5 units."""
    units = unit_service.get_all_units(db)
    return templates.TemplateResponse(
        request=request,
        name="units/list.html",
        context={"page_title": "Units & Owners", "units": units},
    )


@router.get("/{unit_id}", response_class=HTMLResponse)
async def unit_detail(unit_id: int, request: Request, db: Session = Depends(get_db)):
    """Display a single unit and all its contacts."""
    unit = unit_service.get_unit(db, unit_id)
    return templates.TemplateResponse(
        request=request,
        name="units/detail.html",
        context={"page_title": f"Unit {unit.unit_number}", "unit": unit},
    )


@router.get("/{unit_id}/edit", response_class=HTMLResponse)
async def edit_unit_form(unit_id: int, request: Request, db: Session = Depends(get_db)):
    """Display the edit form for a unit."""
    unit = unit_service.get_unit(db, unit_id)
    return templates.TemplateResponse(
        request=request,
        name="units/edit_unit.html",
        context={"page_title": f"Edit Unit {unit.unit_number}", "unit": unit},
    )


@router.post("/{unit_id}/edit")
async def edit_unit_submit(
    unit_id: int,
    description: str = Form(default=""),
    participation_quota: float = Form(...),
    db: Session = Depends(get_db),
):
    """Save changes to a unit and redirect back to the detail page."""
    unit_service.update_unit(
        db,
        unit_id,
        description=description.strip() or None,
        participation_quota=participation_quota / 100,  # form submits as %, store as decimal
    )
    return RedirectResponse(url=f"/units/{unit_id}", status_code=303)


@router.get("/{unit_id}/contacts/add", response_class=HTMLResponse)
async def add_contact_form(unit_id: int, request: Request, db: Session = Depends(get_db)):
    """Display the add contact form for a unit."""
    unit = unit_service.get_unit(db, unit_id)
    return templates.TemplateResponse(
        request=request,
        name="units/add_contact.html",
        context={"page_title": "Add Contact", "unit": unit},
    )


@router.post("/{unit_id}/contacts/add")
async def add_contact_submit(
    unit_id: int,
    name: str = Form(...),
    phone: str = Form(default=""),
    email: str = Form(default=""),
    is_owner: bool = Form(default=False),
    is_tenant: bool = Form(default=False),
    is_resident: bool = Form(default=False),
    is_trustee: bool = Form(default=False),
    db: Session = Depends(get_db),
):
    """Save a new contact and redirect back to the unit detail page."""
    unit_service.create_contact(
        db,
        unit_id=unit_id,
        name=name.strip(),
        phone=phone.strip() or None,
        email=email.strip() or None,
        is_owner=is_owner,
        is_tenant=is_tenant,
        is_resident=is_resident,
        is_trustee=is_trustee,
    )
    return RedirectResponse(url=f"/units/{unit_id}", status_code=303)


@router.get("/{unit_id}/contacts/{contact_id}/edit", response_class=HTMLResponse)
async def edit_contact_form(
    unit_id: int, contact_id: int, request: Request, db: Session = Depends(get_db)
):
    """Display the edit form for a contact."""
    unit = unit_service.get_unit(db, unit_id)
    contact = unit_service.get_contact(db, contact_id)
    return templates.TemplateResponse(
        request=request,
        name="units/edit_contact.html",
        context={"page_title": "Edit Contact", "unit": unit, "contact": contact},
    )


@router.post("/{unit_id}/contacts/{contact_id}/edit")
async def edit_contact_submit(
    unit_id: int,
    contact_id: int,
    name: str = Form(...),
    phone: str = Form(default=""),
    email: str = Form(default=""),
    is_owner: bool = Form(default=False),
    is_tenant: bool = Form(default=False),
    is_resident: bool = Form(default=False),
    is_trustee: bool = Form(default=False),
    db: Session = Depends(get_db),
):
    """Save contact changes and redirect back to the unit detail page."""
    unit_service.update_contact(
        db,
        contact_id=contact_id,
        name=name.strip(),
        phone=phone.strip() or None,
        email=email.strip() or None,
        is_owner=is_owner,
        is_tenant=is_tenant,
        is_resident=is_resident,
        is_trustee=is_trustee,
    )
    return RedirectResponse(url=f"/units/{unit_id}", status_code=303)


@router.post("/{unit_id}/contacts/{contact_id}/delete")
async def delete_contact(
    unit_id: int, contact_id: int, db: Session = Depends(get_db)
):
    """Delete a contact and redirect back to the unit detail page."""
    unit_service.delete_contact(db, contact_id)
    return RedirectResponse(url=f"/units/{unit_id}", status_code=303)
