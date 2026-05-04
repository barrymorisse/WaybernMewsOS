"""
Routes for Module 11: Insurance Documents.

GET  /insurance                                   — policy list page
POST /insurance/policies                          — create a new policy → redirect to detail
GET  /insurance/clear-modal                       — HTMX: returns empty string to clear modal overlay
GET  /insurance/{policy_id}                       — policy detail page
GET  /insurance/{policy_id}/key-facts             — HTMX partial: key facts card (re-fetched on documentChanged)
GET  /insurance/{policy_id}/documents             — HTMX partial: document list (re-fetched on docListRefresh)
GET  /insurance/{policy_id}/delete-confirm        — HTMX: loads policy delete confirmation modal
POST /insurance/{policy_id}/delete                — cascade-delete policy + all documents → redirect
POST /insurance/{policy_id}/documents             — upload a new document (PDF)
POST /insurance/{policy_id}/chat                  — Q&A: ask a question about the documents
GET  /insurance/documents/{doc_id}/pdf            — serve a saved PDF inline
GET  /insurance/documents/{doc_id}/delete-confirm — HTMX: loads document delete confirmation modal
POST /insurance/documents/{doc_id}/delete         — delete a single document

HTMX refresh strategy:
  - After upload: router returns updated document list (outerHTML target) + HX-Trigger: keyFactsRefresh
  - After doc delete: router returns empty + HX-Trigger: {"docListRefresh": true, "keyFactsRefresh": true}
  - Key facts card and doc list listen for their respective triggers and auto-refetch.
  - Modal is cleared by targeting #modal-overlay with empty response.
"""

import json
import os

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.insurance import InsuranceDocument, InsurancePolicy
from app.services import insurance_service as svc

router = APIRouter(prefix="/insurance", tags=["insurance"])

templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
)

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

# Human-readable labels for document type codes
DOC_TYPE_LABELS = {
    "policy": "Policy Document",
    "renewal_schedule": "Renewal Schedule",
    "sasria": "SASRIA Cover Note",
    "broker": "Broker Document",
    "other": "Other",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_policy_or_404(db: Session, policy_id: int) -> InsurancePolicy:
    policy = db.query(InsurancePolicy).filter(InsurancePolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


def _get_doc_or_404(db: Session, doc_id: int) -> InsuranceDocument:
    doc = db.query(InsuranceDocument).filter(InsuranceDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


def _all_policies(db: Session) -> list[InsurancePolicy]:
    return (
        db.query(InsurancePolicy)
        .order_by(InsurancePolicy.cover_start_date.desc().nullslast())
        .all()
    )


# ---------------------------------------------------------------------------
# Policy list
# ---------------------------------------------------------------------------

@router.get("", response_class=HTMLResponse)
async def insurance_index(request: Request, db: Session = Depends(get_db)):
    """Main insurance page: lists all policy periods."""
    policies = _all_policies(db)
    return templates.TemplateResponse(
        request=request,
        name="insurance/index.html",
        context={
            "page_title": "Insurance",
            "policies": policies,
            "doc_type_labels": DOC_TYPE_LABELS,
        },
    )


# ---------------------------------------------------------------------------
# New policy form (loaded inline via HTMX)
# ---------------------------------------------------------------------------

@router.get("/new-policy-form", response_class=HTMLResponse)
async def new_policy_form(request: Request):
    """Return the inline new-policy form partial."""
    return templates.TemplateResponse(
        request=request,
        name="insurance/partials/new_policy_form.html",
        context={},
    )


# ---------------------------------------------------------------------------
# Create policy
# ---------------------------------------------------------------------------

@router.post("/policies")
async def create_policy(
    label: str = Form(...),
    insurer_name: str = Form(""),
    policy_number: str = Form(""),
    cover_start_date: str = Form(""),
    cover_end_date: str = Form(""),
    total_premium: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    """Create a new insurance policy record and redirect to its detail page."""
    from datetime import date

    def _parse_date(s: str):
        s = s.strip()
        if not s:
            return None
        try:
            return date.fromisoformat(s)
        except ValueError:
            return None

    def _parse_decimal(s: str):
        s = s.strip().replace(",", "").replace("R", "").replace(" ", "")
        if not s:
            return None
        try:
            from decimal import Decimal
            return Decimal(s)
        except Exception:
            return None

    policy = InsurancePolicy(
        label=label.strip(),
        insurer_name=insurer_name.strip() or None,
        policy_number=policy_number.strip() or None,
        cover_start_date=_parse_date(cover_start_date),
        cover_end_date=_parse_date(cover_end_date),
        total_premium=_parse_decimal(total_premium),
        notes=notes.strip() or None,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)

    return RedirectResponse(url=f"/insurance/{policy.id}", status_code=303)


# ---------------------------------------------------------------------------
# Policy detail
# ---------------------------------------------------------------------------

@router.get("/{policy_id}", response_class=HTMLResponse)
async def policy_detail(policy_id: int, request: Request, db: Session = Depends(get_db)):
    """Policy detail page: key facts card, document list, upload form, chat."""
    policy = _get_policy_or_404(db, policy_id)
    merged_facts = svc.merge_key_facts(policy.documents)

    return templates.TemplateResponse(
        request=request,
        name="insurance/detail.html",
        context={
            "page_title": policy.label,
            "policy": policy,
            "merged_facts": merged_facts,
            "doc_type_labels": DOC_TYPE_LABELS,
            "doc_type_options": list(DOC_TYPE_LABELS.items()),
        },
    )


# ---------------------------------------------------------------------------
# HTMX partials — auto-refreshed via HX-Trigger events
# ---------------------------------------------------------------------------

@router.get("/{policy_id}/key-facts", response_class=HTMLResponse)
async def key_facts_partial(policy_id: int, request: Request, db: Session = Depends(get_db)):
    """Return the key facts card partial (re-fetched when keyFactsRefresh fires)."""
    policy = _get_policy_or_404(db, policy_id)
    merged_facts = svc.merge_key_facts(policy.documents)

    return templates.TemplateResponse(
        request=request,
        name="insurance/partials/key_facts_card.html",
        context={"policy": policy, "merged_facts": merged_facts},
    )


@router.get("/{policy_id}/documents", response_class=HTMLResponse)
async def document_list_partial(policy_id: int, request: Request, db: Session = Depends(get_db)):
    """Return the document list partial (re-fetched when docListRefresh fires)."""
    policy = _get_policy_or_404(db, policy_id)

    return templates.TemplateResponse(
        request=request,
        name="insurance/partials/document_list.html",
        context={
            "policy": policy,
            "doc_type_labels": DOC_TYPE_LABELS,
            "doc_type_options": list(DOC_TYPE_LABELS.items()),
        },
    )


# ---------------------------------------------------------------------------
# Clear modal
# ---------------------------------------------------------------------------

@router.get("/clear-modal", response_class=HTMLResponse)
async def clear_modal():
    """Return empty HTML to clear the modal overlay. Called by Cancel buttons."""
    return HTMLResponse(content="")


# ---------------------------------------------------------------------------
# Policy delete confirm modal + delete
# ---------------------------------------------------------------------------

@router.get("/{policy_id}/delete-confirm", response_class=HTMLResponse)
async def policy_delete_confirm(policy_id: int, request: Request, db: Session = Depends(get_db)):
    """Return the delete confirmation modal partial for a policy."""
    policy = _get_policy_or_404(db, policy_id)
    doc_count = len(policy.documents)

    return templates.TemplateResponse(
        request=request,
        name="insurance/partials/confirm_modal.html",
        context={
            "title": "Delete Policy",
            "message": (
                f"Delete <strong>{policy.label}</strong>?"
                + (
                    f" This will permanently delete the policy and all "
                    f"<strong>{doc_count} linked document{'s' if doc_count != 1 else ''}</strong> "
                    f"and their files."
                    if doc_count > 0
                    else " This will permanently delete the policy."
                )
                + " This cannot be undone."
            ),
            "confirm_url": f"/insurance/{policy_id}/delete",
            "confirm_label": "Delete Policy",
            "cancel_url": "/insurance/clear-modal",
        },
    )


@router.post("/{policy_id}/delete")
async def delete_policy(policy_id: int, db: Session = Depends(get_db)):
    """
    Cascade-delete a policy and all its documents.
    Files on disk are deleted before the DB record is removed.
    Redirects to the policy list.
    """
    policy = _get_policy_or_404(db, policy_id)

    # Delete files from disk before removing DB records
    for doc in policy.documents:
        if doc.file_path:
            abs_path = os.path.join(_PROJECT_ROOT, doc.file_path)
            if os.path.exists(abs_path):
                os.remove(abs_path)

    db.delete(policy)
    db.commit()

    return RedirectResponse(url="/insurance", status_code=303)


# ---------------------------------------------------------------------------
# Document upload
# ---------------------------------------------------------------------------

@router.post("/{policy_id}/documents", response_class=HTMLResponse)
async def upload_document(
    policy_id: int,
    request: Request,
    document_name: str = Form(...),
    document_type: str = Form(...),
    pdf_file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload a PDF, extract text + key facts, save to disk and DB.

    Returns the updated document list partial + HX-Trigger: keyFactsRefresh
    so the key facts card auto-refreshes. On error, returns the document list
    with an error banner.
    """
    policy = _get_policy_or_404(db, policy_id)

    if not pdf_file.filename.lower().endswith(".pdf"):
        return _document_list_response(
            request, policy,
            error="Only PDF files can be uploaded. Please select a .pdf file."
        )

    file_bytes = await pdf_file.read()

    # --- Save PDF to disk ---
    try:
        file_path = svc.save_pdf(
            file_bytes, policy_id, document_type, pdf_file.filename
        )
    except Exception as e:
        return _document_list_response(
            request, policy,
            error=f"Could not save the file: {e}"
        )

    # --- Extract text ---
    extracted_text, page_count = svc.extract_text_with_pages(file_bytes)
    text_warning = None
    if extracted_text is None:
        text_warning = (
            "Document saved, but no text could be extracted — it may be a scanned/image-based PDF. "
            "You can still view the PDF, but it won't be included in Q&A."
        )

    # --- Extract key facts via Groq ---
    key_facts_json = None
    key_facts_warning = None
    if extracted_text:
        try:
            facts = svc.extract_key_facts(extracted_text)
            key_facts_json = json.dumps(facts)
        except RuntimeError as e:
            key_facts_warning = (
                f"Document saved, but key facts could not be extracted — the LLM call failed: {e}. "
                "You can still view the PDF and use Q&A."
            )

    # --- Save DB record ---
    doc = InsuranceDocument(
        policy_id=policy_id,
        document_name=document_name.strip(),
        document_type=document_type,
        file_path=file_path,
        page_count=page_count,
        extracted_text=extracted_text,
        key_facts_json=key_facts_json,
    )
    db.add(doc)
    db.commit()

    # Refresh policy to pick up the new document
    db.refresh(policy)

    warning = text_warning or key_facts_warning

    return _document_list_response(
        request, policy,
        warning=warning,
        trigger_key_facts=True,
    )


def _document_list_response(
    request,
    policy,
    error: str | None = None,
    warning: str | None = None,
    trigger_key_facts: bool = False,
) -> HTMLResponse:
    """Render the document list partial and return it as an HTMLResponse."""
    html = templates.TemplateResponse(
        request=request,
        name="insurance/partials/document_list.html",
        context={
            "policy": policy,
            "doc_type_labels": DOC_TYPE_LABELS,
            "doc_type_options": list(DOC_TYPE_LABELS.items()),
            "upload_error": error,
            "upload_warning": warning,
        },
    )
    headers = {}
    if trigger_key_facts:
        headers["HX-Trigger"] = "keyFactsRefresh"
    return HTMLResponse(content=html.body.decode(), headers=headers)


# ---------------------------------------------------------------------------
# Document delete confirm modal + delete
# ---------------------------------------------------------------------------

@router.get("/documents/{doc_id}/delete-confirm", response_class=HTMLResponse)
async def document_delete_confirm(doc_id: int, request: Request, db: Session = Depends(get_db)):
    """Return the delete confirmation modal partial for a single document."""
    doc = _get_doc_or_404(db, doc_id)

    return templates.TemplateResponse(
        request=request,
        name="insurance/partials/confirm_modal.html",
        context={
            "title": "Delete Document",
            "message": (
                f"Delete <strong>{doc.document_name}</strong>? "
                "This will permanently remove the file and its extracted data. "
                "This cannot be undone."
            ),
            "confirm_url": f"/insurance/documents/{doc_id}/delete",
            "confirm_label": "Delete Document",
            "cancel_url": "/insurance/clear-modal",
            "confirm_target": "#document-list-container",
            "confirm_swap": "outerHTML",
        },
    )


@router.post("/documents/{doc_id}/delete", response_class=HTMLResponse)
async def delete_document(doc_id: int, db: Session = Depends(get_db)):
    """
    Delete a single document: remove the file from disk and the DB record.

    Returns empty HTML (clears the modal) and fires HX-Trigger events so
    the document list and key facts card auto-refresh.
    """
    doc = _get_doc_or_404(db, doc_id)

    # Delete file from disk
    if doc.file_path:
        abs_path = os.path.join(_PROJECT_ROOT, doc.file_path)
        if os.path.exists(abs_path):
            os.remove(abs_path)

    db.delete(doc)
    db.commit()

    # Fire both refresh events: document list + key facts card
    return HTMLResponse(
        content="",
        headers={"HX-Trigger": json.dumps({"docListRefresh": True, "keyFactsRefresh": True})},
    )


# ---------------------------------------------------------------------------
# Serve PDF
# ---------------------------------------------------------------------------

@router.get("/documents/{doc_id}/pdf")
async def serve_pdf(doc_id: int, db: Session = Depends(get_db)):
    """Serve a saved insurance PDF inline in the browser."""
    doc = _get_doc_or_404(db, doc_id)

    if not doc.file_path:
        raise HTTPException(status_code=404, detail="No file stored for this document")

    abs_path = os.path.join(_PROJECT_ROOT, doc.file_path)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=abs_path,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline"},
    )


# ---------------------------------------------------------------------------
# Q&A chat
# ---------------------------------------------------------------------------

@router.post("/{policy_id}/chat", response_class=HTMLResponse)
async def chat(
    policy_id: int,
    request: Request,
    question: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Answer a plain-language question about the policy documents.
    Returns a chat response partial appended to the chat history area.
    """
    policy = _get_policy_or_404(db, policy_id)

    # Build Q&A context from all documents that have extracted text
    context = svc.build_qa_context(policy.documents)
    if not context:
        answer = "No document text is available to answer questions. Please upload at least one readable PDF."
    else:
        answer = svc.ask_question(context, question.strip())

    return templates.TemplateResponse(
        request=request,
        name="insurance/partials/chat_response.html",
        context={"question": question.strip(), "answer": answer},
    )
