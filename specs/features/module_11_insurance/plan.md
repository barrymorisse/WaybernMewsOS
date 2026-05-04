# plan.md — Module 11: Insurance Documents

## Plan

---

### Task Group 1 — Data Layer

1. Create `app/models/insurance.py` with SQLAlchemy models for `InsurancePolicy` and `InsuranceDocument`.
2. Import the new models in `app/database.py` (or wherever `Base.metadata.create_all` is called) so the tables are created on startup.
3. Add `documents/insurance/` to the directory structure (create on first use; add to `.gitignore` alongside other document folders).

---

### Task Group 2 — PDF & LLM Service

Create `app/services/insurance_service.py` containing:

1. **`extract_text_with_pages(pdf_path) -> tuple[str, int]`**
   - Open PDF with pypdf, iterate pages, prefix each with `\n\n[Page N]\n`
   - Return `(full_text, page_count)`
   - On extraction failure, return `(None, 0)` and log the error

2. **`extract_key_facts(document_name, extracted_text) -> dict`**
   - Groq API call (llama-3.3-70b-versatile, temperature=0)
   - System prompt: instructs the model to extract a fixed set of fields as JSON — insurer name, policy number, cover start, cover end, total premium (ZAR), main covers (list), key exclusions (list), claims excess, emergency contact number, any other critical facts
   - Returns parsed dict; on failure returns `{}`

3. **`merge_key_facts(documents: list[InsuranceDocument]) -> dict`**
   - Iterates documents in upload order, merging each document's `key_facts_json` dict
   - Later values override earlier ones for the same key
   - Returns merged dict for display in the key facts card

4. **`build_qa_context(documents: list[InsuranceDocument]) -> str`**
   - Concatenates extracted text of all documents with a header per document:
     `=== {document_name} ===\n{extracted_text}`
   - Returns the full context string for the Q&A prompt

5. **`ask_question(context: str, question: str) -> str`**
   - Groq API call (llama-3.3-70b-versatile, temperature=0)
   - System prompt: instructs the model to answer using only the provided documents, cite `[Page N]` references, and note when information cannot be found rather than guessing
   - Returns the answer string
   - On Groq API error, returns a user-friendly error message

---

### Task Group 3 — Backend Routes

Create `app/routers/insurance.py`:

1. **`GET /insurance`** — list all insurance policies, render `insurance/index.html`
2. **`GET /insurance/new`** — render form to create a new policy (partial for HTMX modal or inline)
3. **`POST /insurance/policies`** — create policy record, redirect to `/insurance/{id}`
4. **`GET /insurance/{policy_id}`** — policy detail page: load policy + documents + merged key facts, render `insurance/detail.html`
5. **`POST /insurance/{policy_id}/documents`** — handle document upload:
   - Save PDF to `documents/insurance/`
   - Extract text + page count
   - Extract key facts via Groq
   - Save `InsuranceDocument` record
   - Return HTMX partial refreshing the document list and key facts card
6. **`GET /insurance/documents/{doc_id}/pdf`** — serve PDF via `FileResponse` (inline, new tab)
7. **`DELETE /insurance/documents/{doc_id}`** — delete DB record + file, return HTMX partial refreshing document list and key facts card
8. **`POST /insurance/{policy_id}/chat`** — receive question, build context, call Groq, return answer as HTMX partial rendered into the response area

Register the router in `main.py`.

---

### Task Group 4 — Templates

Create `templates/insurance/`:

1. **`index.html`** — extends base layout
   - Page heading "Insurance"
   - "New Policy" button → opens inline form or modal
   - Policy list: each row shows label, insurer, cover dates, document count, link to detail page
   - Empty state message if no policies exist

2. **`detail.html`** — extends base layout
   - Back link to `/insurance`
   - Policy header (label, insurer, cover dates, policy number, total premium)
   - **Key facts card**: structured grid showing merged key facts (insurer, cover dates, premium, main covers, key exclusions, excess, emergency contact). Empty-state message if no documents uploaded.
   - **Documents section**: table of uploaded documents (name, type, pages, uploaded date, View PDF link, delete button). Upload form below the table (name, type dropdown, file input, submit button).
   - **Chat section**: text input + "Ask" button. Response area below (initially empty). HTMX posts to `/insurance/{policy_id}/chat` and swaps the response area with the returned partial.

3. **`partials/document_list.html`** — HTMX-swappable partial for the document table (used after upload and delete)
4. **`partials/key_facts_card.html`** — HTMX-swappable partial for the key facts card (refreshed after upload/delete)
5. **`partials/chat_response.html`** — HTMX-swappable partial rendered into the chat response area

---

### Task Group 5 — Sidebar & Navigation

1. Add "Insurance" link to the sidebar in `templates/base.html`, positioned after the existing nav items.
2. Highlight active state when the current path starts with `/insurance`.

---

### Task Group 6 — Testing & Validation

1. Create a new insurance policy via the UI and confirm it appears in the list.
2. Upload each of the 5 real insurance documents and verify:
   - PDF is saved to `documents/insurance/`
   - Extracted text contains `[Page N]` markers and reads coherently
   - Key facts card updates after each upload with sensible values
3. Ask 5-6 representative questions and verify:
   - Answers are grounded in the document content
   - Page citations appear in responses
   - Clicking "View PDF" opens the correct document
4. Test the scanned/unreadable PDF edge case by attempting to upload an image-only PDF.
5. Delete a document and confirm the key facts card updates and the file is removed from disk.
6. Confirm no existing pages or features are broken.
