# plan.md — Module 2b: CoJ Bill Parsing

## Status: Complete

All task groups delivered. Both Phase 1 (parse and display) and Phase 2 (save to DB) are built and running.

---

## Task Group 1 — Data Layer ✅

- `app/models/coj_invoice.py`: `CojInvoice` and `CojInvoiceLineItem` SQLAlchemy models
- `app/models/complex_settings.py`: `ComplexSettings` singleton model (account numbers, meter numbers)
- `app/models/__init__.py`: all models imported so `create_all()` picks them up
- `app/database.py`: `_apply_migrations()` handles ADD COLUMN and DROP COLUMN on every startup — safe to run repeatedly

---

## Task Group 2 — Parsing Service ✅

`app/services/coj_parsing.py`:

- `extract_text_from_pdf(file_bytes)` — pypdf, raises ValueError if no text extracted
- `ELECTRICITY_PROMPT` / `WATER_PROMPT` — prompts with explicit multi-step and line-break examples
- `build_prompt(invoice_type, raw_text)` — selects correct prompt and appends raw text
- `call_groq(prompt)` — Groq API call at temperature=0; strips markdown fences from response if present
- `compute_step_costs(extracted)` — adds computed cost (usage × rate) to each step using Python Decimal
- `run_checks(extracted, steps, invoice_type, expected_account, expected_meter)` — returns list of check result dicts with label, pass, severity ("error"/"warning"), message
- `parse_invoice(file_bytes, invoice_type, expected_account, expected_meter)` — orchestrates full pipeline; returns success dict or error dict

Six checks implemented:
1. Invoice totals (error, ±R0.10)
2. Account number match (error, skipped-as-warning if not configured)
3. Meter number match (error, skipped-as-warning if not configured)
4. Consumption arithmetic: end − start = consumption (error)
5. Step usage sum = consumption (error)
6. VAT rate ≈ 15% (warning, ±R1.00)

---

## Task Group 3 — Persistence Service ✅

`app/services/coj_persistence.py`:

- `billing_period(statement_year, statement_month)` — returns (billing_year, billing_month), one month behind
- `save_pdf(invoice_type, year, month, pdf_bytes)` — writes to `documents/invoices/`, returns relative path
- `write_invoice(db, invoice_type, extracted, steps, pdf_path)` — creates `CojInvoice` + all `CojInvoiceLineItem` rows and commits
- `save_temp(...)` / `load_temp(key)` / `delete_temp(key)` — temp file management for the overwrite-confirmation flow (UUID-keyed JSON in `/tmp/`)

---

## Task Group 4 — Router ✅

`app/routers/coj_invoices.py`:

- `GET /coj-invoices` — upload page
- `POST /coj-invoices/parse` — runs pipeline; auto-saves if all error checks pass; returns conflict partial if duplicate found
- `POST /coj-invoices/overwrite` — deletes old record, writes new, saves PDF, cleans up temp
- `POST /coj-invoices/cancel-overwrite` — deletes temp, returns neutral message

`app/routers/complex_info.py`:

- `GET /complex-info` — full Complex Info page
- `GET /complex-info/view` — HTMX partial: read-only view (used by Cancel button)
- `GET /complex-info/edit` — HTMX partial: edit form
- `POST /complex-info` — saves settings, returns read-only view partial

---

## Task Group 5 — UI ✅

Templates created:

| Template | Purpose |
|----------|---------|
| `coj_invoices/upload.html` | Upload page with radio toggle, file input, HTMX form, spinner |
| `coj_invoices/results.html` | Full results: saved banner, validation summary, individual checks list, invoice header, charges table, DB record panel, debug panel |
| `coj_invoices/conflict.html` | Duplicate confirmation: comparison table, Overwrite / Keep existing buttons |
| `coj_invoices/kept.html` | Neutral message after user chooses to keep existing record |
| `coj_invoices/error.html` | Parse or upload error with optional raw text panel |
| `complex_info/index.html` | Complex Info full page |
| `complex_info/_view.html` | Read-only partial: account + meter numbers for both services |
| `complex_info/_edit.html` | Edit form partial: inline HTMX swap |

Sidebar additions:
- "CoJ Invoices" nav link (document icon)
- "Complex Info" nav link below a divider (gear icon)

---

## Task Group 6 — Invoice History & PDF Access ✅

`app/routers/coj_invoices.py`:
- `GET /coj-invoices` updated to query all saved invoices and pass to template
- `GET /coj-invoices/list` — HTMX partial returning the list (used for auto-refresh)
- `GET /coj-invoices/{invoice_id}/pdf` — serves the saved PDF via `FileResponse` (inline, opens in new tab)
- Parse and overwrite endpoints now send `HX-Trigger: invoiceSaved` response header on successful save so the list refreshes without a page reload

Templates:
- `coj_invoices/_invoice_list.html` — list partial used by both initial render (Jinja2 include) and HTMX refresh; shows type badge, statement month, billing period, invoice number, total due, save date, PDF link
- `coj_invoices/upload.html` — restructured: upload form (`max-w-2xl`) + results area above, full-width saved invoices section below with HTMX auto-refresh trigger

---

## Task Group 7 — Testing & Validation ✅

- April 2026 electricity invoice parsed correctly; all checks pass
- April 2026 water invoice parsed correctly (3 steps from single-line format); all checks pass
- Duplicate handling tested: comparison UI shows, overwrite and cancel both work
- Account number and meter number checks run once configured in Complex Info
- DB record panel confirms correct rows written with invoice_id FK linkage visible
- PDF saved to `documents/invoices/` with deterministic filename
- Saved invoices list displays correctly after upload; refreshes automatically on save
- PDF "Open" link serves file inline in new browser tab
