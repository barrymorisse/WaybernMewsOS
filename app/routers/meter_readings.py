"""
Routes for Module 2a: Meter Readings.

List, add, and edit monthly meter readings.
GET routes render templates; POST routes process forms and redirect.
"""

import calendar
from datetime import date
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from fastapi import HTTPException
import os

from app.database import get_db
from app.services import meter_readings as reading_service

router = APIRouter(prefix="/meter-readings", tags=["meter-readings"])

templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
)

# Pass month names to templates so they can render "April 2026" instead of "4 2026"
MONTH_NAMES = list(calendar.month_name)  # ["", "January", "February", ...]


@router.get("", response_class=HTMLResponse)
async def readings_list(request: Request, db: Session = Depends(get_db)):
    """Display all monthly readings, newest first."""
    readings = reading_service.get_all_readings(db)
    return templates.TemplateResponse(
        request=request,
        name="meter_readings/list.html",
        context={
            "page_title": "Meter Readings",
            "readings": readings,
            "month_names": MONTH_NAMES,
        },
    )


@router.get("/add", response_class=HTMLResponse)
async def add_reading_form(request: Request):
    """Display a blank form for adding a new monthly reading."""
    today = date.today()
    return templates.TemplateResponse(
        request=request,
        name="meter_readings/form.html",
        context={
            "page_title": "Add Meter Reading",
            "reading": None,
            "month_names": MONTH_NAMES,
            "current_year": today.year,
            "current_month": today.month,
            "action": "/meter-readings/add",
            "error": None,
        },
    )


@router.post("/add")
async def add_reading_submit(
    request: Request,
    db: Session = Depends(get_db),
    year: int = Form(...),
    month: int = Form(...),
    reading_date: str = Form(...),
    elec_unit_1: str = Form(default=""),
    elec_unit_2: str = Form(default=""),
    elec_unit_3: str = Form(default=""),
    elec_unit_4: str = Form(default=""),
    elec_unit_5: str = Form(default=""),
    elec_public_lighting: str = Form(default=""),
    elec_total: str = Form(default=""),
    water_unit_1: str = Form(default=""),
    water_unit_2: str = Form(default=""),
    water_unit_3: str = Form(default=""),
    water_unit_4: str = Form(default=""),
    water_unit_5: str = Form(default=""),
    water_total: str = Form(default=""),
):
    """Save a new monthly reading. Re-renders the form with an error on duplicate month."""
    data = {
        "year": year, "month": month, "reading_date": reading_date,
        "elec_unit_1": elec_unit_1, "elec_unit_2": elec_unit_2,
        "elec_unit_3": elec_unit_3, "elec_unit_4": elec_unit_4,
        "elec_unit_5": elec_unit_5, "elec_public_lighting": elec_public_lighting,
        "elec_total": elec_total, "water_unit_1": water_unit_1,
        "water_unit_2": water_unit_2, "water_unit_3": water_unit_3,
        "water_unit_4": water_unit_4, "water_unit_5": water_unit_5,
        "water_total": water_total,
    }
    try:
        reading_service.create_reading(db, data)
    except HTTPException as e:
        # Re-render the form with the error message and the values the user entered
        return templates.TemplateResponse(
            request=request,
            name="meter_readings/form.html",
            context={
                "page_title": "Add Meter Reading",
                "reading": data,  # repopulate the form with submitted values
                "month_names": MONTH_NAMES,
                "current_year": year,
                "current_month": month,
                "action": "/meter-readings/add",
                "error": e.detail,
            },
        )
    return RedirectResponse(url="/meter-readings", status_code=303)


@router.get("/{reading_id}/edit", response_class=HTMLResponse)
async def edit_reading_form(reading_id: int, request: Request, db: Session = Depends(get_db)):
    """Display the edit form pre-filled with an existing reading's values."""
    reading = reading_service.get_reading(db, reading_id)
    return templates.TemplateResponse(
        request=request,
        name="meter_readings/form.html",
        context={
            "page_title": f"Edit Reading — {MONTH_NAMES[reading.month]} {reading.year}",
            "reading": reading,
            "month_names": MONTH_NAMES,
            "current_year": reading.year,
            "current_month": reading.month,
            "action": f"/meter-readings/{reading_id}/edit",
            "error": None,
        },
    )


@router.post("/{reading_id}/edit")
async def edit_reading_submit(
    reading_id: int,
    reading_date: str = Form(...),
    elec_unit_1: str = Form(default=""),
    elec_unit_2: str = Form(default=""),
    elec_unit_3: str = Form(default=""),
    elec_unit_4: str = Form(default=""),
    elec_unit_5: str = Form(default=""),
    elec_public_lighting: str = Form(default=""),
    elec_total: str = Form(default=""),
    water_unit_1: str = Form(default=""),
    water_unit_2: str = Form(default=""),
    water_unit_3: str = Form(default=""),
    water_unit_4: str = Form(default=""),
    water_unit_5: str = Form(default=""),
    water_total: str = Form(default=""),
    db: Session = Depends(get_db),
):
    """Save changes to an existing reading and redirect to the list."""
    data = {
        "reading_date": reading_date,
        "elec_unit_1": elec_unit_1, "elec_unit_2": elec_unit_2,
        "elec_unit_3": elec_unit_3, "elec_unit_4": elec_unit_4,
        "elec_unit_5": elec_unit_5, "elec_public_lighting": elec_public_lighting,
        "elec_total": elec_total, "water_unit_1": water_unit_1,
        "water_unit_2": water_unit_2, "water_unit_3": water_unit_3,
        "water_unit_4": water_unit_4, "water_unit_5": water_unit_5,
        "water_total": water_total,
    }
    reading_service.update_reading(db, reading_id, data)
    return RedirectResponse(url="/meter-readings", status_code=303)
