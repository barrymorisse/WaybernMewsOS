"""
Routes for the Complex Info settings page.

GET  /complex-info       — full page (read-only view)
GET  /complex-info/view  — HTMX partial: read-only view (used by Cancel button)
GET  /complex-info/edit  — HTMX partial: edit form
POST /complex-info       — save changes, return HTMX partial: read-only view
"""

import os
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.complex_settings import ComplexSettings

router = APIRouter(prefix="/complex-info", tags=["complex-info"])

templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
)


def _get_or_create(db: Session) -> ComplexSettings:
    settings = db.query(ComplexSettings).filter(ComplexSettings.id == 1).first()
    if not settings:
        settings = ComplexSettings(id=1, electricity_account_number=None, water_account_number=None)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@router.get("", response_class=HTMLResponse)
async def complex_info_page(request: Request, db: Session = Depends(get_db)):
    settings = _get_or_create(db)
    return templates.TemplateResponse(
        request=request,
        name="complex_info/index.html",
        context={"page_title": "Complex Info", "settings": settings},
    )


@router.get("/view", response_class=HTMLResponse)
async def complex_info_view(request: Request, db: Session = Depends(get_db)):
    settings = _get_or_create(db)
    return templates.TemplateResponse(
        request=request,
        name="complex_info/_view.html",
        context={"settings": settings},
    )


@router.get("/edit", response_class=HTMLResponse)
async def complex_info_edit(request: Request, db: Session = Depends(get_db)):
    settings = _get_or_create(db)
    return templates.TemplateResponse(
        request=request,
        name="complex_info/_edit.html",
        context={"settings": settings},
    )


@router.post("", response_class=HTMLResponse)
async def complex_info_save(
    request: Request,
    db: Session = Depends(get_db),
    electricity_account_number: str = Form(""),
    electricity_meter_number: str = Form(""),
    water_account_number: str = Form(""),
    water_meter_number: str = Form(""),
):
    settings = _get_or_create(db)
    settings.electricity_account_number = electricity_account_number.strip() or None
    settings.electricity_meter_number = electricity_meter_number.strip() or None
    settings.water_account_number = water_account_number.strip() or None
    settings.water_meter_number = water_meter_number.strip() or None
    db.commit()
    db.refresh(settings)
    return templates.TemplateResponse(
        request=request,
        name="complex_info/_view.html",
        context={"settings": settings},
    )
