"""
Service for Module 11: Insurance Documents.

Handles:
  1. PDF text extraction with [Page N] markers (for citations in Q&A answers)
  2. Key facts extraction via Groq (one call per document on upload)
  3. Merging key facts across all documents in a policy (for the summary card)
  4. Q&A context building and LLM question answering

No database interaction here — pure document and LLM logic.
"""

import io
import json
import os
import time

from pypdf import PdfReader
from groq import Groq


# ---------------------------------------------------------------------------
# Project root — used to construct absolute file paths for saving/serving PDFs
# ---------------------------------------------------------------------------

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Directory where insurance PDFs are stored (relative to project root)
INSURANCE_DOCS_DIR = os.path.join(_PROJECT_ROOT, "documents", "insurance")


# ---------------------------------------------------------------------------
# 1. PDF text extraction
# ---------------------------------------------------------------------------

def extract_text_with_pages(file_bytes: bytes) -> tuple[str | None, int]:
    """
    Extract text from a PDF, inserting [Page N] markers between pages.

    Returns (full_text, page_count).
    Returns (None, page_count) if the PDF yields no readable text
    (e.g. scanned/image-based PDF — it's saved but excluded from Q&A).
    """
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        page_count = len(reader.pages)
        parts = []
        for i, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            if text and text.strip():
                parts.append(f"[Page {i}]\n{text.strip()}")

        if not parts:
            return None, page_count

        return "\n\n".join(parts), page_count

    except Exception:
        return None, 0


# ---------------------------------------------------------------------------
# 2. Save PDF to disk
# ---------------------------------------------------------------------------

def save_pdf(file_bytes: bytes, policy_id: int, document_type: str, original_filename: str) -> str:
    """
    Save a PDF to documents/insurance/ and return the relative path for DB storage.

    Filename pattern: {policy_id}_{document_type}_{timestamp}.pdf
    The timestamp prevents filename collisions on re-upload.
    """
    os.makedirs(INSURANCE_DOCS_DIR, exist_ok=True)

    # Strip the extension from the original filename for the stem
    stem = os.path.splitext(original_filename)[0]
    # Sanitise: replace spaces and special chars with underscores
    stem = "".join(c if c.isalnum() or c in "-_" else "_" for c in stem)
    timestamp = int(time.time())

    filename = f"{policy_id}_{document_type}_{timestamp}_{stem}.pdf"
    abs_path = os.path.join(INSURANCE_DOCS_DIR, filename)

    with open(abs_path, "wb") as f:
        f.write(file_bytes)

    # Return path relative to project root for DB storage
    return os.path.join("documents", "insurance", filename)


# ---------------------------------------------------------------------------
# 3. Key facts extraction via Groq
# ---------------------------------------------------------------------------

_KEY_FACTS_PROMPT = """You are extracting key facts from an insurance document for a small residential body corporate in Johannesburg, South Africa.

Extract the following fields from the document text below. If a field is not found in this specific document, use null.

Return ONLY valid JSON with exactly this structure — no explanation, no markdown, no code fences:

{
  "insurer": "name of the insurance company or null",
  "policy_number": "policy or schedule number or null",
  "cover_start_date": "YYYY-MM-DD or null",
  "cover_end_date": "YYYY-MM-DD or null",
  "total_annual_premium": "amount as a string e.g. 'R 45,230.00' or null",
  "total_insured_value": "total sum insured / replacement value as a string e.g. 'R 12,500,000' or null",
  "main_covers": ["list of main cover types covered by this policy, e.g. 'Fire and allied perils', 'Special risks', 'Public liability'"],
  "key_exclusions": ["list of notable exclusions mentioned in this document"],
  "claims_excess": "description of the standard excess e.g. 'R 5,000 per event' or null",
  "emergency_contact": "emergency or after-hours claims contact number or email or null",
  "broker_name": "name of the insurance broker or null",
  "broker_contact": "broker phone number or email or null"
}

Document text:
"""


def extract_key_facts(extracted_text: str) -> dict:
    """
    Call Groq to extract structured key facts from a document's extracted text.

    Returns a dict of key facts on success.
    Raises RuntimeError on API failure (caller decides how to handle — document
    is always saved regardless, error is shown to the user).
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set. Please add it to your .env file.")

    client = Groq(api_key=api_key)

    # Truncate to ~80,000 characters to stay comfortably within the 128k token context window
    text_to_send = extracted_text[:80000]
    prompt = _KEY_FACTS_PROMPT + text_to_send

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise data extraction assistant. Return only valid JSON, nothing else.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=1000,
        )
    except Exception as e:
        raise RuntimeError(f"Groq API request failed: {e}")

    content = response.choices[0].message.content.strip()

    # Strip markdown code fences if the model added them despite instructions
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(
            line for line in lines if not line.strip().startswith("```")
        ).strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Return empty dict rather than raising — the document is still usable
        return {}


# ---------------------------------------------------------------------------
# 4. Merge key facts across all documents in a policy
# ---------------------------------------------------------------------------

def merge_key_facts(documents) -> dict:
    """
    Merge key facts from all documents for a policy into a single summary dict.

    Rules:
    - Documents are processed in upload order (oldest first).
    - For scalar fields: later non-null values override earlier ones.
    - For list fields (main_covers, key_exclusions): items are combined and deduplicated.
    - Null values never override existing non-null values.
    """
    merged = {}

    for doc in documents:
        if not doc.key_facts_json:
            continue
        try:
            facts = json.loads(doc.key_facts_json)
        except (json.JSONDecodeError, TypeError):
            continue

        for key, value in facts.items():
            if isinstance(value, list):
                # Combine lists, preserving order and deduplicating
                existing = merged.get(key) or []
                for item in value:
                    if item and item not in existing:
                        existing.append(item)
                merged[key] = existing
            elif value is not None and value != "":
                # Later non-null values override earlier ones
                merged[key] = value
            elif key not in merged:
                # Only set null/empty if we haven't seen this key yet
                merged[key] = value

    return merged


# ---------------------------------------------------------------------------
# 5. Q&A — build context and ask questions
# ---------------------------------------------------------------------------

_QA_SYSTEM_PROMPT = """You are an expert insurance policy analyst helping the chairperson of a small residential body corporate in Johannesburg, South Africa understand their insurance documents.

Answer questions based ONLY on the provided document text. When you reference specific information, always cite the source using the format [Page N — Document Name]. If there are multiple relevant pages, cite all of them.

If the answer cannot be found in the documents, say so clearly — never guess or make up information.

Be concise and practical. Use plain language. Format your answer clearly, using bullet points where helpful."""


def build_qa_context(documents) -> str:
    """
    Concatenate extracted text of all documents with clear section headers.
    The [Page N] markers in each document's text are preserved so the LLM
    can include them in citations.
    """
    parts = []
    for doc in documents:
        if doc.extracted_text:
            parts.append(f"=== {doc.document_name} ===\n\n{doc.extracted_text}")

    if not parts:
        return ""

    separator = "\n\n" + "=" * 60 + "\n\n"
    return separator.join(parts)


def ask_question(context: str, question: str) -> str:
    """
    Send a plain-language question about the insurance documents to Groq.

    Returns the answer string (with page citations from the LLM).
    Returns a user-friendly error message string on failure — never raises.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return "Something went wrong — GROQ_API_KEY is not set. Please add it to your .env file."

    # Truncate context to ~100,000 characters (~75k tokens) to stay within limits
    context_to_send = context[:100000]

    client = Groq(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": _QA_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Here are the insurance documents:\n\n{context_to_send}"
                        f"\n\n{'=' * 60}\n\nQuestion: {question}"
                    ),
                },
            ],
            temperature=0,
            max_tokens=2000,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        return (
            f"Something went wrong — the LLM could not process your request. "
            f"Please try again in a moment.\n\nTechnical detail: {e}"
        )
