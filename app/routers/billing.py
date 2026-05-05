"""
Routes for Module 2c: Utility Consumption & Allocation.

GET  /utility-billing                           — list of all billing periods
GET  /utility-billing/{year}/{month}            — detail page with full workings
POST /utility-billing/{year}/{month}/recalculate — overwrite existing calculation
"""

import calendar
import os
from itertools import groupby

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.billing import BillingCalculation
from app.models.coj_invoice import CojInvoice
from app.models.meter_readings import MeterReading
from app.services import billing_service

router = APIRouter(prefix="/utility-billing", tags=["utility-billing"])

templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
)

MONTH_NAMES = list(calendar.month_name)  # ["", "January", "February", ...]


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

    # Load meter readings for the current and previous month
    reading = db.query(MeterReading).filter_by(year=billing_year, month=billing_month).first()
    prev_year  = billing_year if billing_month > 1 else billing_year - 1
    prev_month = billing_month - 1 if billing_month > 1 else 12
    prev_reading = db.query(MeterReading).filter_by(year=prev_year, month=prev_month).first()

    # Load CoJ invoices
    elec_inv  = db.query(CojInvoice).filter_by(
        billing_year=billing_year, billing_month=billing_month, invoice_type="electricity"
    ).first()
    water_inv = db.query(CojInvoice).filter_by(
        billing_year=billing_year, billing_month=billing_month, invoice_type="water"
    ).first()

    # Determine what's missing (for "not yet calculated" message)
    missing = []
    if not reading:
        missing.append("meter readings")
    if not elec_inv:
        missing.append("electricity invoice")
    if not water_inv:
        missing.append("water & sanitation invoice")

    # Group step allocations by invoice_type then step_number for the template
    elec_steps_grouped = []
    water_steps_grouped = []
    if calculation:
        elec_rows  = [r for r in calculation.step_allocations if r.invoice_type == "electricity"]
        water_rows = [r for r in calculation.step_allocations if r.invoice_type == "water"]
        elec_steps_grouped  = _group_steps(elec_rows)
        water_steps_grouped = _group_steps(water_rows)

    # Identify sewer charge for display in fixed costs section
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
        elec_steps_grouped = _group_steps(elec_rows)

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
        water_steps_grouped = _group_steps(water_rows)
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


@router.post("/{billing_year}/{billing_month}/recalculate", response_class=HTMLResponse)
async def recalculate(
    billing_year: int,
    billing_month: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Force a fresh calculation, overwriting any existing result."""
    try:
        billing_service.run_calculation(billing_year, billing_month, db)
    except ValueError as e:
        # Return an error partial — the modal will display this
        return templates.TemplateResponse(
            request=request,
            name="billing/_recalc_error.html",
            context={"error": str(e)},
        )

    # Redirect to the detail page (HTMX will follow the HX-Redirect header)
    from fastapi.responses import Response
    response = Response(status_code=204)
    response.headers["HX-Redirect"] = f"/utility-billing/{billing_year}/{billing_month}"
    return response


# ---------------------------------------------------------------------------
# Private helper
# ---------------------------------------------------------------------------

def _group_steps(rows: list) -> list[dict]:
    """
    Group BillingStepAllocation rows by step_number.
    Returns a list of dicts: [{step_number, step_label, consumers: [row, ...]}, ...]
    """
    groups = []
    for step_num, step_rows in groupby(rows, key=lambda r: r.step_number):
        step_rows_list = list(step_rows)
        groups.append({
            "step_number": step_num,
            "step_label":  step_rows_list[0].step_label,
            "consumers":   step_rows_list,
            "total_usage": sum(r.usage_allocated or 0 for r in step_rows_list),
            "total_cost":  sum(r.cost or 0 for r in step_rows_list),
        })
    return groups
