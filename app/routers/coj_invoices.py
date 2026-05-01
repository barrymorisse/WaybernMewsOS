"""
Routes for Module 2b: CoJ Bill Parsing.

GET  /coj-invoices                — upload page + saved invoices list
GET  /coj-invoices/list           — HTMX partial: saved invoices list (auto-refreshed after save)
GET  /coj-invoices/{id}/pdf       — serve a saved invoice PDF inline
POST /coj-invoices/parse          — parse PDF; writes to DB if all checks pass, or shows conflict
POST /coj-invoices/overwrite      — confirm overwrite of an existing record
POST /coj-invoices/cancel-overwrite — discard pending overwrite, keep existing record
"""

import calendar
import os
from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.coj_invoice import CojInvoice
from app.models.complex_settings import ComplexSettings
from app.services.coj_parsing import parse_invoice
from app.services.coj_persistence import (
    billing_period, delete_temp, load_temp, save_pdf, save_temp, write_invoice,
    _PROJECT_ROOT,
)

router = APIRouter(prefix="/coj-invoices", tags=["coj-invoices"])

templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
)

MONTH_NAMES = list(calendar.month_name)  # ["", "January", "February", ...]


def _expected_refs(db: Session, invoice_type: str) -> tuple[str | None, str | None]:
    """Return (expected_account_number, expected_meter_number) for the given invoice type."""
    settings = db.query(ComplexSettings).filter(ComplexSettings.id == 1).first()
    if not settings:
        return None, None
    if invoice_type == "electricity":
        return settings.electricity_account_number, settings.electricity_meter_number
    return settings.water_account_number, settings.water_meter_number


def _saved_invoices(db: Session) -> list[CojInvoice]:
    """Return all saved invoices ordered newest statement first."""
    return (
        db.query(CojInvoice)
        .order_by(
            CojInvoice.statement_year.desc(),
            CojInvoice.statement_month.desc(),
            CojInvoice.invoice_type,
        )
        .all()
    )


def _results_context(result: dict, invoice_type: str, saved: bool = False) -> dict:
    """Build the context dict shared by all paths that render results.html."""
    extracted = result["extracted"]
    checks = result["checks"]
    totals_check = next((c for c in checks if c["label"] == "Invoice totals"), None)
    steps_subtotal = totals_check["breakdown"]["steps_total"] if totals_check else 0.0
    bill_year, bill_month = billing_period(extracted["statement_year"], extracted["statement_month"])
    return {
        "invoice_type": invoice_type,
        "invoice_type_label": "Electricity" if invoice_type == "electricity" else "Water & Sanitation",
        "extracted": extracted,
        "steps": result["steps"],
        "checks": checks,
        "all_errors_pass": result["all_errors_pass"],
        "steps_subtotal": steps_subtotal,
        "anomalies": result["anomalies"],
        "raw_text": result["raw_text"],
        "month_names": MONTH_NAMES,
        "saved": saved,
        "billing_year": bill_year,
        "billing_month": bill_month,
        "invoice_id": None,
    }


@router.get("", response_class=HTMLResponse)
async def upload_page(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="coj_invoices/upload.html",
        context={
            "page_title": "CoJ Invoices",
            "invoices": _saved_invoices(db),
            "month_names": MONTH_NAMES,
        },
    )


@router.get("/list", response_class=HTMLResponse)
async def invoice_list(request: Request, db: Session = Depends(get_db)):
    """HTMX partial — returns the saved invoices list for auto-refresh after a save."""
    return templates.TemplateResponse(
        request=request,
        name="coj_invoices/_invoice_list.html",
        context={
            "invoices": _saved_invoices(db),
            "month_names": MONTH_NAMES,
        },
    )


@router.get("/{invoice_id}/pdf")
async def download_pdf(invoice_id: int, db: Session = Depends(get_db)):
    """Serve a saved invoice PDF inline in the browser."""
    invoice = db.query(CojInvoice).filter(CojInvoice.id == invoice_id).first()
    if not invoice or not invoice.pdf_path:
        raise HTTPException(status_code=404, detail="PDF not found")

    abs_path = os.path.join(_PROJECT_ROOT, invoice.pdf_path)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="PDF file not found on disk")

    return FileResponse(abs_path, media_type="application/pdf")


@router.post("/parse", response_class=HTMLResponse)
async def parse_invoice_upload(
    request: Request,
    db: Session = Depends(get_db),
    invoice_type: str = Form(...),
    pdf_file: UploadFile = File(...),
):
    if not pdf_file.filename.lower().endswith(".pdf"):
        return templates.TemplateResponse(
            request=request,
            name="coj_invoices/error.html",
            context={
                "error": f'"{pdf_file.filename}" is not a PDF file. Please upload a .pdf file.',
                "raw_text": None,
            },
        )

    file_bytes = await pdf_file.read()
    expected_account, expected_meter = _expected_refs(db, invoice_type)
    result = parse_invoice(file_bytes, invoice_type, expected_account, expected_meter)

    if not result["success"]:
        return templates.TemplateResponse(
            request=request,
            name="coj_invoices/error.html",
            context={"error": result["error"], "raw_text": result.get("raw_text")},
        )

    if not result["all_errors_pass"]:
        return templates.TemplateResponse(
            request=request,
            name="coj_invoices/results.html",
            context=_results_context(result, invoice_type, saved=False),
        )

    extracted = result["extracted"]
    existing = db.query(CojInvoice).filter(
        CojInvoice.invoice_type == invoice_type,
        CojInvoice.statement_year == extracted["statement_year"],
        CojInvoice.statement_month == extracted["statement_month"],
    ).first()

    if existing:
        temp_key = save_temp(
            invoice_type=invoice_type,
            extracted=extracted,
            steps=result["steps"],
            checks=result["checks"],
            anomalies=result["anomalies"],
            raw_text=result["raw_text"],
            pdf_bytes=file_bytes,
        )
        bill_year, bill_month = billing_period(extracted["statement_year"], extracted["statement_month"])
        return templates.TemplateResponse(
            request=request,
            name="coj_invoices/conflict.html",
            context={
                "temp_key": temp_key,
                "invoice_type": invoice_type,
                "invoice_type_label": "Electricity" if invoice_type == "electricity" else "Water & Sanitation",
                "existing": existing,
                "new_extracted": extracted,
                "month_names": MONTH_NAMES,
                "bill_year": bill_year,
                "bill_month": bill_month,
            },
        )

    pdf_path = save_pdf(invoice_type, extracted["statement_year"], extracted["statement_month"], file_bytes)
    invoice = write_invoice(db, invoice_type, extracted, result["steps"], pdf_path)

    ctx = _results_context(result, invoice_type, saved=True)
    ctx["invoice_id"] = invoice.id
    return templates.TemplateResponse(
        request=request,
        name="coj_invoices/results.html",
        context=ctx,
        headers={"HX-Trigger": "invoiceSaved"},
    )


@router.post("/overwrite", response_class=HTMLResponse)
async def overwrite_invoice(
    request: Request,
    db: Session = Depends(get_db),
    temp_key: str = Form(...),
    invoice_type: str = Form(...),
):
    try:
        payload = load_temp(temp_key)
    except FileNotFoundError:
        return templates.TemplateResponse(
            request=request,
            name="coj_invoices/error.html",
            context={"error": "The pending parse result has expired. Please upload the PDF again.", "raw_text": None},
        )

    extracted = payload["extracted"]

    db.query(CojInvoice).filter(
        CojInvoice.invoice_type == invoice_type,
        CojInvoice.statement_year == extracted["statement_year"],
        CojInvoice.statement_month == extracted["statement_month"],
    ).delete()
    db.commit()

    import base64
    pdf_bytes = base64.b64decode(payload["pdf_bytes_b64"])
    pdf_path = save_pdf(invoice_type, extracted["statement_year"], extracted["statement_month"], pdf_bytes)
    invoice = write_invoice(db, invoice_type, extracted, payload["steps"], pdf_path)
    delete_temp(temp_key)

    result = {
        "extracted": extracted,
        "steps": payload["steps"],
        "checks": payload["checks"],
        "all_errors_pass": True,
        "anomalies": payload["anomalies"],
        "raw_text": payload["raw_text"],
    }
    ctx = _results_context(result, invoice_type, saved=True)
    ctx["invoice_id"] = invoice.id
    return templates.TemplateResponse(
        request=request,
        name="coj_invoices/results.html",
        context=ctx,
        headers={"HX-Trigger": "invoiceSaved"},
    )


@router.post("/cancel-overwrite", response_class=HTMLResponse)
async def cancel_overwrite(
    request: Request,
    temp_key: str = Form(...),
):
    delete_temp(temp_key)
    return templates.TemplateResponse(
        request=request,
        name="coj_invoices/kept.html",
        context={},
    )
