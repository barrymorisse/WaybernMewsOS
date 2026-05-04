# requirements.md — Module 11: Insurance Documents
**Status: ✅ Complete — built 2026-05-04**


## Overview

A module for storing, reading, and querying complex insurance documents using a plain-language chat interface powered by an LLM. Barry can upload PDFs linked to a policy period, see key facts extracted automatically on upload, and ask questions about the documents in plain English — with answers that cite specific page numbers.

---

## Problem

Insurance documents are long, verbose, and difficult to interpret. During a renewal cycle Barry needs to understand what is and isn't covered, what the excesses are, and how the SASRIA cover works — information buried across hundreds of pages of legal text. Currently this requires manually reading through PDFs, which is time-consuming and stressful, especially under time pressure from a broker.

---

## Goals

1. Store insurance PDFs linked to a named policy period (e.g. 1 June 2026 – 31 May 2027).
2. Manage documents from the UI (upload, view, delete).
3. Automatically extract a structured key facts summary on every upload, displayed as a card.
4. Enable plain-language Q&A against all documents for the active policy, with page-level citations in the answers.
5. Allow viewing of original PDFs inline in the browser.

---

## Non-Goals

- Claims tracking or management.
- Premium payment tracking.
- Broker contact management (can be added later).
- Persistent chat history (fresh session each time is sufficient).
- Policy comparison across years (future enhancement).
- Saved/bookmarked answers.

---

## Constraints

- Must work offline except for LLM calls (Groq API requires internet).
- No new Python dependencies beyond what is already installed. pypdf and the `groq` library are already in use.
- Groq free tier may have rate limits for large inputs. If this becomes a problem in practice, the LLM call is swapped to Claude Haiku (`claude-haiku-4-5`) via `ANTHROPIC_API_KEY` — a one-line change in the service file.
- PDFs are stored in `documents/insurance/` and served inline via FastAPI (same pattern as Module 2b).
- All currency is ZAR.

---

## Key Decisions

### Text extraction strategy
Extract PDF text on upload using pypdf, inserting `[Page N]` markers between pages. Store the extracted text in the database (`insurance_documents.extracted_text`). This means the DB is the source of truth for querying — the PDF is kept only for human viewing. Re-parsing on every query is avoided.

### Key facts extraction
On each document upload, make one Groq API call to extract a structured set of key facts from that document's text. Store as JSON in `insurance_documents.key_facts_json`. The policy detail page merges key facts across all documents (later-uploaded documents override earlier ones for the same key) to produce one unified "key facts" card.

### Q&A context
When Barry asks a question, concatenate the extracted text of all documents linked to the active policy, with clear document headers (e.g. `=== Policy Document [Page 1] ... ===`). Send this as context to Groq along with the question. Estimated total input is ~64,000 tokens, within Groq's 128k context window.

### Citations
The LLM prompt instructs the model to cite `[Page N]` references in its answers. Barry can then open the PDF viewer and navigate to that page manually.

### Policy periods
Policies are stored as records with a start date, end date, and label (e.g. "2026–2027 Renewal"). Documents are linked to a policy. This supports future year-on-year comparison.

### No chat history
Each chat session is stateless — previous questions are not sent as context. This keeps token usage minimal and is sufficient for Barry's use case.

---

## Data Model Impact

### New table: `insurance_policies`

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| label | String | e.g. "2026–2027 Renewal" |
| insurer_name | String | |
| policy_number | String | nullable |
| cover_start_date | Date | |
| cover_end_date | Date | |
| total_premium | Numeric | nullable, ZAR |
| notes | Text | nullable |
| created_at | DateTime | |

### New table: `insurance_documents`

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| policy_id | Integer FK → insurance_policies | |
| document_name | String | e.g. "Policy Schedule", "SASRIA Cover Note" |
| document_type | String | enum: policy, renewal_schedule, sasria, broker, other |
| file_path | String | relative path under `documents/insurance/` |
| page_count | Integer | |
| extracted_text | Text | pypdf output with [Page N] markers |
| key_facts_json | Text | JSON string of extracted key facts |
| uploaded_at | DateTime | |

### No changes to existing tables.

---

## User Flow

1. Barry clicks "Insurance" in the sidebar.
2. The Insurance page lists all policy periods. A button at the top opens a form to create a new policy period.
3. Barry clicks on a policy period to open the policy detail page.
4. The top of the detail page shows the **key facts card** — a structured summary merged from all uploaded documents (insurer, policy number, cover dates, total premium, main covers, key exclusions, claims excess).
5. Below the card is the **documents list** — each document shows its name, type, page count, upload date, and a "View PDF" link. A delete button is present on each document row.
   - Clicking delete on a **document** triggers a confirmation modal: "Delete [document name]? This will permanently remove the file and its extracted data. This cannot be undone." Options: Cancel / Delete. On confirm, the document record and file are deleted and the page updates via HTMX.
   - Clicking delete on a **policy** (from the insurance list page) triggers a confirmation modal: "Delete [policy label]? This will permanently delete the policy and all [N] linked documents and their files. This cannot be undone." Options: Cancel / Delete. On confirm, the policy and all its documents and files are cascade deleted.
6. An **upload form** at the bottom of the documents list lets Barry add a new document: name it, select a type, and upload the PDF. On submit:
   - PDF is saved to `documents/insurance/{policy_id}_{filename}.pdf`
   - Text is extracted via pypdf with page markers
   - Groq extracts key facts (one API call)
   - Record saved to DB
   - Page refreshes to show the updated document list and key facts card
7. Below the documents section is the **chat interface**: a text input, a submit button, and a response area. Barry types a question and submits (HTMX POST).
8. The response area shows the LLM's answer, including page citations (e.g. "The excess for fire damage is R10,000 [Page 47 — Policy Document]").
9. Clicking "View PDF" on any document opens the PDF inline in a new browser tab.

---

## Edge Cases

- **pypdf fails to extract text** (e.g. scanned/image-based PDF): Show a clear error on upload. Store the document but mark `extracted_text` as null and exclude it from Q&A context. Inform Barry the document cannot be queried but can still be viewed.
- **Groq key facts extraction fails on upload**: Save the document anyway with `key_facts_json` as null. Show a visible warning banner on the page after upload: "Document saved, but key facts could not be extracted — the LLM call failed. You can still view the PDF and use Q&A." The key facts card omits any fields it does not have data for.
- **Groq Q&A call fails**: Display a visible error message in the chat response area: "Something went wrong — the LLM could not process your request. Please try again in a moment." Never show a blank response or silently fail.
- **Duplicate filename on upload**: Append a timestamp to the filename to avoid collisions.
- **No documents uploaded yet**: Key facts card shows an empty state message. Chat interface is disabled with a tooltip: "Upload at least one document to enable Q&A."
- **Policy deleted with documents attached**: Modal warns Barry that all linked documents and files will be permanently deleted. Barry must confirm before the cascade delete proceeds. A policy with zero documents shows a simpler modal with no cascade warning.

---

## Risks

- **Groq free tier rate limits** for 64k-token inputs are the primary technical risk. Mitigation: Claude Haiku fallback is a one-line swap, costs ~R1 per question.
- **pypdf text quality**: Some insurance PDFs use complex layouts or embedded fonts that extract poorly. Mitigation: display extracted text preview on upload so Barry can see if it looks reasonable.
- **LLM hallucination**: The model may occasionally state something confidently that isn't in the documents. Mitigation: page citations allow Barry to verify any answer directly.
