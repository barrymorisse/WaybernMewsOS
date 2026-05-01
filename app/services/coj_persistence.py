"""
Persistence service for Module 2b: CoJ Bill Parsing.

Handles writing a parsed invoice to the database and saving its PDF to disk.
Also manages the temporary file used to hold parse results during the
overwrite-confirmation flow.
"""

import base64
import json
import os
import tempfile
import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.models.coj_invoice import CojInvoice, CojInvoiceLineItem

# Absolute path to documents/invoices/ relative to the project root
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INVOICES_DIR = os.path.join(_PROJECT_ROOT, "documents", "invoices")


# ---------------------------------------------------------------------------
# Billing period helper
# ---------------------------------------------------------------------------

def billing_period(statement_year: int, statement_month: int) -> tuple[int, int]:
    """Return (billing_year, billing_month) — one calendar month before the statement."""
    if statement_month == 1:
        return statement_year - 1, 12
    return statement_year, statement_month - 1


# ---------------------------------------------------------------------------
# PDF storage
# ---------------------------------------------------------------------------

def pdf_filename(invoice_type: str, statement_year: int, statement_month: int) -> str:
    return f"{invoice_type}_{statement_year}_{statement_month:02d}.pdf"


def save_pdf(invoice_type: str, statement_year: int, statement_month: int, pdf_bytes: bytes) -> str:
    """
    Write the PDF bytes to documents/invoices/ and return the relative path
    (relative to the project root) for storage in the DB.
    """
    os.makedirs(INVOICES_DIR, exist_ok=True)
    filename = pdf_filename(invoice_type, statement_year, statement_month)
    abs_path = os.path.join(INVOICES_DIR, filename)
    with open(abs_path, "wb") as f:
        f.write(pdf_bytes)
    return os.path.join("documents", "invoices", filename)


# ---------------------------------------------------------------------------
# Database write
# ---------------------------------------------------------------------------

def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        parts = s.split("-")
        return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except Exception:
        return None


def write_invoice(
    db: Session,
    invoice_type: str,
    extracted: dict,
    steps: list[dict],
    pdf_path: str | None,
) -> CojInvoice:
    """
    Create a new CojInvoice + line items and commit to the database.
    The caller is responsible for ensuring no duplicate already exists
    (or for deleting the existing record first in the overwrite case).
    """
    bill_year, bill_month = billing_period(
        extracted["statement_year"], extracted["statement_month"]
    )

    invoice = CojInvoice(
        invoice_type=invoice_type,
        statement_year=extracted["statement_year"],
        statement_month=extracted["statement_month"],
        billing_year=bill_year,
        billing_month=bill_month,
        invoice_date=_parse_date(extracted.get("invoice_date")),
        invoice_number=extracted.get("invoice_number"),
        account_number=extracted.get("account_number"),
        payment_due_date=_parse_date(extracted.get("payment_due_date")),
        reading_period_start=_parse_date(extracted.get("reading_period_start")),
        reading_period_end=_parse_date(extracted.get("reading_period_end")),
        start_reading=extracted.get("start_reading"),
        end_reading=extracted.get("end_reading"),
        consumption=extracted.get("consumption"),
        total_vat=extracted.get("total_vat"),
        total_due=extracted.get("total_due"),
        pdf_path=pdf_path,
        status="saved",
    )
    db.add(invoice)
    db.flush()  # populate invoice.id before inserting line items

    for i, step in enumerate(steps):
        db.add(CojInvoiceLineItem(
            invoice_id=invoice.id,
            line_type="step",
            label=step["label"],
            usage_amount=step["usage_amount"],
            rate=step["rate"],
            cost=step["cost"],
            sort_order=i,
        ))

    for i, charge in enumerate(extracted.get("fixed_charges", [])):
        db.add(CojInvoiceLineItem(
            invoice_id=invoice.id,
            line_type="fixed",
            label=charge["label"],
            usage_amount=None,
            rate=None,
            cost=charge["cost"],
            sort_order=len(steps) + i,
        ))

    db.commit()
    db.refresh(invoice)
    return invoice


# ---------------------------------------------------------------------------
# Temp file management (used during the overwrite-confirmation flow)
# ---------------------------------------------------------------------------

def _temp_path(key: str) -> str:
    return os.path.join(tempfile.gettempdir(), f"waybern_parse_{key}.json")


def save_temp(
    invoice_type: str,
    extracted: dict,
    steps: list,
    checks: list,
    anomalies: list,
    raw_text: str,
    pdf_bytes: bytes,
) -> str:
    """Serialise parse results + PDF bytes to a temp file. Returns the lookup key."""
    key = str(uuid.uuid4())
    payload = {
        "invoice_type": invoice_type,
        "extracted": extracted,
        "steps": steps,
        "checks": checks,
        "anomalies": anomalies,
        "raw_text": raw_text,
        "pdf_bytes_b64": base64.b64encode(pdf_bytes).decode("ascii"),
    }
    with open(_temp_path(key), "w") as f:
        json.dump(payload, f)
    return key


def load_temp(key: str) -> dict:
    """Load a previously saved temp payload. Raises FileNotFoundError if expired/missing."""
    with open(_temp_path(key), "r") as f:
        return json.load(f)


def delete_temp(key: str) -> None:
    try:
        os.remove(_temp_path(key))
    except FileNotFoundError:
        pass
