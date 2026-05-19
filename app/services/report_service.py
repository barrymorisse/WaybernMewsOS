"""
Module 2d: Billing Calculation Report generator.

generate_billing_report(year, month, db) -> str | None
  Renders billing/report.html to PDF via WeasyPrint, saves to
  documents/utility_calculations/utility_calculation_{year}_{month:02d}.pdf,
  updates pdf_path and pdf_generated_at on the BillingCalculation row,
  and returns the saved path.  Returns None if PDF generation fails (the
  calculation record is preserved either way).
"""

import calendar
import logging
import os
from datetime import datetime
from itertools import groupby

from jinja2 import Environment, FileSystemLoader
from sqlalchemy.orm import Session

from app.models.billing import BillingCalculation
from app.models.coj_invoice import CojInvoice
from app.models.meter_readings import MeterReading

logger = logging.getLogger(__name__)

_BASE_DIR      = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_TEMPLATES_DIR = os.path.join(_BASE_DIR, "app", "templates")
_STATIC_DIR    = os.path.join(_BASE_DIR, "static")
_OUTPUT_DIR    = os.path.join(_BASE_DIR, "documents", "utility_calculations")
_MONTH_NAMES   = list(calendar.month_name)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_billing_report(year: int, month: int, db: Session) -> str | None:
    """
    Generate (or regenerate) the PDF report for one billing month.
    Returns the PDF file path on success, None on failure.
    """
    try:
        return _generate(year, month, db)
    except Exception as exc:
        logger.error("PDF generation failed for %d-%02d: %s", year, month, exc, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Template helpers — also imported by the billing router
# ---------------------------------------------------------------------------

def group_steps(rows: list) -> list[dict]:
    """Group BillingStepAllocation rows by step_number for template rendering."""
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


def reading_rows(reading, prev_reading, prefix: str) -> list[dict]:
    """Build pre-processed consumer reading rows for the report template."""
    rows = []
    for n in range(1, 6):
        rows.append({
            "label":       f"Unit {n}",
            "prev":        getattr(prev_reading, f"{prefix}_unit_{n}", None) if prev_reading else None,
            "curr":        getattr(reading,      f"{prefix}_unit_{n}", None) if reading      else None,
            "consumption": getattr(reading,      f"{prefix}_unit_{n}_consumption", None) if reading else None,
            "adjusted":    getattr(reading,      f"{prefix}_unit_{n}_adjusted",    None) if reading else None,
        })
    rows.append({
        "label":       "Common Property",
        "prev":        None,
        "curr":        None,
        "consumption": getattr(reading, f"{prefix}_common_consumption", None) if reading else None,
        "adjusted":    getattr(reading, f"{prefix}_common_adjusted",    None) if reading else None,
    })
    return rows


# ---------------------------------------------------------------------------
# Private implementation
# ---------------------------------------------------------------------------

def _fmt(value, decimals=2) -> str:
    try:
        return f"{float(value):,.{decimals}f}".replace(",", " ")
    except (ValueError, TypeError):
        return "—"


def _get_jinja_env() -> Environment:
    env = Environment(loader=FileSystemLoader(_TEMPLATES_DIR), autoescape=False)
    env.filters["fmt"] = _fmt
    return env


def _generate(year: int, month: int, db: Session) -> str:
    import weasyprint  # imported here so a missing install gives a clear error at call time

    calc = (
        db.query(BillingCalculation)
        .filter_by(billing_year=year, billing_month=month)
        .first()
    )
    if not calc:
        raise ValueError(f"No billing calculation found for {year}-{month:02d}")

    reading = db.query(MeterReading).filter_by(year=year, month=month).first()
    prev_year  = year if month > 1 else year - 1
    prev_month = month - 1 if month > 1 else 12
    prev_reading = db.query(MeterReading).filter_by(year=prev_year, month=prev_month).first()

    elec_inv = db.query(CojInvoice).filter_by(
        billing_year=year, billing_month=month, invoice_type="electricity"
    ).first()
    water_inv = db.query(CojInvoice).filter_by(
        billing_year=year, billing_month=month, invoice_type="water"
    ).first()

    elec_rows  = [r for r in calc.step_allocations if r.invoice_type == "electricity"]
    water_rows = [r for r in calc.step_allocations if r.invoice_type == "water"]

    water_fixed_all = [li for li in (water_inv.line_items if water_inv else []) if li.line_type == "fixed"]
    sewer_charge    = next((li for li in water_fixed_all if li.label.lower().strip() == "sewer charge"), None)

    elec_step_items  = {li.label: li for li in (elec_inv.line_items  if elec_inv  else []) if li.line_type == "step"}
    water_step_items = {li.label: li for li in (water_inv.line_items if water_inv else []) if li.line_type == "step"}

    context = {
        "billing_year":        year,
        "billing_month":       month,
        "month_names":         _MONTH_NAMES,
        "calculation":         calc,
        "unit_allocations":    calc.unit_allocations,
        "elec_steps_grouped":  group_steps(elec_rows),
        "water_steps_grouped": group_steps(water_rows),
        "elec_step_items":     elec_step_items,
        "water_step_items":    water_step_items,
        "reading":             reading,
        "prev_reading":        prev_reading,
        "elec_inv":            elec_inv,
        "water_inv":           water_inv,
        "elec_fixed_items":    [li for li in (elec_inv.line_items if elec_inv else []) if li.line_type == "fixed"],
        "water_fixed_items":   [li for li in water_fixed_all if li.label.lower().strip() != "sewer charge"],
        "sewer_charge":        sewer_charge,
        "elec_reading_rows":   reading_rows(reading, prev_reading, "elec"),
        "water_reading_rows":  reading_rows(reading, prev_reading, "water"),
        "generated_at":        datetime.now(),
    }

    html_string = _get_jinja_env().get_template("billing/report.html").render(**context)

    # WeasyPrint can't resolve URL-path static refs; swap them for file:// absolute paths.
    static_file_base = f"file://{_STATIC_DIR}/"
    html_string = html_string.replace('src="/static/', f'src="{static_file_base}')

    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    pdf_filename = f"utility_calculation_{year}_{month:02d}.pdf"
    pdf_path = os.path.join(_OUTPUT_DIR, pdf_filename)

    weasyprint.HTML(string=html_string).write_pdf(pdf_path)

    calc.pdf_path         = pdf_path
    calc.pdf_generated_at = datetime.now()
    db.commit()

    return pdf_path
