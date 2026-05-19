"""
Routes for Module 2c/2d: Utility Consumption & Allocation + Billing Report.

GET  /utility-billing                              — list of all billing periods
GET  /utility-billing/{year}/{month}               — detail page with full workings
GET  /utility-billing/{year}/{month}/report        — serve the generated PDF inline
POST /utility-billing/{year}/{month}/recalculate   — overwrite existing calculation
"""

import calendar
import os

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.billing import BillingCalculation
from app.models.coj_invoice import CojInvoice
from app.models.meter_readings import MeterReading
from app.services import billing_service
from app.services.report_service import group_steps

from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/utility-billing", tags=["utility-billing"])

templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
)

MONTH_NAMES = list(calendar.month_name)  # ["", "January", "February", ...]


def _fmt(value, decimals=2) -> str:
    """Format a number with space as thousands separator, e.g. 1 234.67."""
    try:
        return f"{float(value):,.{decimals}f}".replace(",", " ")
    except (ValueError, TypeError):
        return "—"

templates.env.filters["fmt"] = _fmt


@router.get("", response_class=HTMLResponse)
async def billing_list(request: Request, db: Session = Depends(get_db)):
    """List all billing periods with their calculation status."""
    periods = billing_service.get_billing_periods(db)
    return templates.TemplateResponse(
        request=request,
        name="billing/index.html",
        context={
            "page_title": "Utility Billing",
            "periods": periods,
            "month_names": MONTH_NAMES,
        },
    )


@router.get("/{billing_year}/{billing_month}", response_class=HTMLResponse)
async def billing_detail(
    billing_year: int,
    billing_month: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Detail page showing full calculation workings for one billing month."""
    calculation = (
        db.query(BillingCalculation)
        .filter_by(billing_year=billing_year, billing_month=billing_month)
        .first()
    )

    reading = db.query(MeterReading).filter_by(year=billing_year, month=billing_month).first()
    prev_year  = billing_year if billing_month > 1 else billing_year - 1
    prev_month = billing_month - 1 if billing_month > 1 else 12
    prev_reading = db.query(MeterReading).filter_by(year=prev_year, month=prev_month).first()

    elec_inv  = db.query(CojInvoice).filter_by(
        billing_year=billing_year, billing_month=billing_month, invoice_type="electricity"
    ).first()
    water_inv = db.query(CojInvoice).filter_by(
        billing_year=billing_year, billing_month=billing_month, invoice_type="water"
    ).first()

    missing = []
    if not reading:
        missing.append("meter readings")
    if not elec_inv:
        missing.append("electricity invoice")
    if not water_inv:
        missing.append("water & sanitation invoice")

    elec_steps_grouped = []
    water_steps_grouped = []
    if calculation:
        elec_rows  = [r for r in calculation.step_allocations if r.invoice_type == "electricity"]
        water_rows = [r for r in calculation.step_allocations if r.invoice_type == "water"]
        elec_steps_grouped  = group_steps(elec_rows)
        water_steps_grouped = group_steps(water_rows)

    sewer_charge = None
    if water_inv:
        for li in water_inv.line_items:
            if li.line_type == "fixed" and li.label.lower().strip() == "sewer charge":
                sewer_charge = li
                break

    return templates.TemplateResponse(
        request=request,
        name="billing/detail.html",
        context={
            "page_title": f"Utility Billing — {MONTH_NAMES[billing_month]} {billing_year}",
            "billing_year":  billing_year,
            "billing_month": billing_month,
            "month_names":   MONTH_NAMES,
            "calculation":   calculation,
            "reading":       reading,
            "prev_reading":  prev_reading,
            "elec_inv":      elec_inv,
            "water_inv":     water_inv,
            "elec_steps_grouped":  elec_steps_grouped,
            "water_steps_grouped": water_steps_grouped,
            "sewer_charge":  sewer_charge,
            "missing":       missing,
        },
    )


@router.get("/{billing_year}/{billing_month}/electricity", response_class=HTMLResponse)
async def billing_electricity(
    billing_year: int,
    billing_month: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Electricity workings detail page for one billing month."""
    calculation = (
        db.query(BillingCalculation)
        .filter_by(billing_year=billing_year, billing_month=billing_month)
        .first()
    )
    reading = db.query(MeterReading).filter_by(year=billing_year, month=billing_month).first()
    prev_year  = billing_year if billing_month > 1 else billing_year - 1
    prev_month = billing_month - 1 if billing_month > 1 else 12
    prev_reading = db.query(MeterReading).filter_by(year=prev_year, month=prev_month).first()
    elec_inv = db.query(CojInvoice).filter_by(
        billing_year=billing_year, billing_month=billing_month, invoice_type="electricity"
    ).first()

    elec_steps_grouped = []
    if calculation:
        elec_rows = [r for r in calculation.step_allocations if r.invoice_type == "electricity"]
        elec_steps_grouped = group_steps(elec_rows)

    return templates.TemplateResponse(
        request=request,
        name="billing/electricity.html",
        context={
            "page_title": f"Electricity — {MONTH_NAMES[billing_month]} {billing_year}",
            "billing_year":  billing_year,
            "billing_month": billing_month,
            "month_names":   MONTH_NAMES,
            "calculation":   calculation,
            "reading":       reading,
            "prev_reading":  prev_reading,
            "elec_inv":      elec_inv,
            "elec_steps_grouped": elec_steps_grouped,
        },
    )


@router.get("/{billing_year}/{billing_month}/water", response_class=HTMLResponse)
async def billing_water(
    billing_year: int,
    billing_month: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Water workings detail page for one billing month."""
    calculation = (
        db.query(BillingCalculation)
        .filter_by(billing_year=billing_year, billing_month=billing_month)
        .first()
    )
    reading = db.query(MeterReading).filter_by(year=billing_year, month=billing_month).first()
    prev_year  = billing_year if billing_month > 1 else billing_year - 1
    prev_month = billing_month - 1 if billing_month > 1 else 12
    prev_reading = db.query(MeterReading).filter_by(year=prev_year, month=prev_month).first()
    water_inv = db.query(CojInvoice).filter_by(
        billing_year=billing_year, billing_month=billing_month, invoice_type="water"
    ).first()

    water_steps_grouped = []
    sewer_charge = None
    if calculation:
        water_rows = [r for r in calculation.step_allocations if r.invoice_type == "water"]
        water_steps_grouped = group_steps(water_rows)
    if water_inv:
        for li in water_inv.line_items:
            if li.line_type == "fixed" and li.label.lower().strip() == "sewer charge":
                sewer_charge = li
                break

    return templates.TemplateResponse(
        request=request,
        name="billing/water.html",
        context={
            "page_title": f"Water — {MONTH_NAMES[billing_month]} {billing_year}",
            "billing_year":  billing_year,
            "billing_month": billing_month,
            "month_names":   MONTH_NAMES,
            "calculation":   calculation,
            "reading":       reading,
            "prev_reading":  prev_reading,
            "water_inv":     water_inv,
            "water_steps_grouped": water_steps_grouped,
            "sewer_charge":  sewer_charge,
        },
    )


@router.get("/{billing_year}/{billing_month}/recalc-modal", response_class=HTMLResponse)
async def recalc_modal(
    billing_year: int,
    billing_month: int,
    request: Request,
):
    """Return the recalculate confirmation modal (loaded into #modal-overlay by HTMX)."""
    return templates.TemplateResponse(
        request=request,
        name="billing/_recalc_modal.html",
        context={
            "billing_year":  billing_year,
            "billing_month": billing_month,
            "month_names":   MONTH_NAMES,
        },
    )


@router.get("/{billing_year}/{billing_month}/report")
async def billing_report_pdf(
    billing_year: int,
    billing_month: int,
    db: Session = Depends(get_db),
):
    """Serve the generated PDF report inline in the browser."""
    from fastapi.responses import FileResponse, Response

    calculation = (
        db.query(BillingCalculation)
        .filter_by(billing_year=billing_year, billing_month=billing_month)
        .first()
    )

    if not calculation or not calculation.pdf_path or not os.path.isfile(calculation.pdf_path):
        return Response(
            content="<p style='font-family:sans-serif;padding:40px'>Report not yet generated for this billing period.</p>",
            media_type="text/html",
            status_code=404,
        )

    return FileResponse(
        path=calculation.pdf_path,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline"},
    )


@router.post("/{billing_year}/{billing_month}/recalculate", response_class=HTMLResponse)
async def recalculate(
    billing_year: int,
    billing_month: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Force a fresh calculation (and regenerate the PDF report), overwriting any existing result."""
    try:
        billing_service.run_calculation(billing_year, billing_month, db)
    except ValueError as e:
        return templates.TemplateResponse(
            request=request,
            name="billing/_recalc_error.html",
            context={"error": str(e)},
        )

    from fastapi.responses import Response
    response = Response(status_code=204)
    response.headers["HX-Redirect"] = f"/utility-billing/{billing_year}/{billing_month}"
    return response
