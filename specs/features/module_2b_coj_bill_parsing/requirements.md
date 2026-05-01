# requirements.md — Module 2b: CoJ Bill Parsing

## Overview

Upload City of Joburg utility bill PDFs (electricity and water & sanitation) via the UI, automatically extract all relevant fields using an LLM, run a suite of validation checks, and — if all checks pass — write the data to the database and save the PDF to the document repository. Duplicate invoices trigger a confirmation UI before overwriting.

---

## Problem

Barry receives two CoJ invoices monthly by email — one for electricity (City Power) and one for water & sanitation (Johannesburg Water, which also includes property rates and refuse on the same PDF). These invoices contain the meter readings and rand amounts needed to calculate per-unit utility billing in Module 2c. Currently these are read and transcribed manually. This module automates that extraction.

---

## Goals

- Upload a CoJ PDF via the UI and have all key fields extracted automatically
- Handle both invoice types (electricity, water & sanitation) through the same upload UI
- Display extracted data in a clear review layout for Barry to verify
- Run a suite of validation checks (totals, account number, meter number, consumption arithmetic, step usage sum, VAT rate) and show each result individually
- Automatically write data to the database and save the PDF if all error-severity checks pass
- Confirm before overwriting if an invoice for the same month already exists
- Store reference data (account numbers, meter numbers) in a Complex Info settings page
- Show a history list of all saved invoices on the CoJ Invoices page
- Allow any saved invoice PDF to be opened directly from the history list

---

## Non-Goals

- Automating email ingestion (future)
- Splitting utility costs across units (Module 2c)
- Verifying start reading against previous month's end reading (future)
- Extracting property rates or refuse data under normal circumstances (both expected to be R0.00)
- Editing individual extracted fields before saving (future)

---

## Constraints

- **Two invoice types:** electricity and water — same upload UI, distinguished by `invoice_type`
- **Variable steps:** 1–4 steps typically; parser handles any number
- **Water invoice has multiple sections:** Property Rates, Water & Sanitation, Refuse — parser extracts Water & Sanitation only
- **Multi-step line format:** When an invoice has more than one step, all steps appear on a single line with a combined total. This applies to both electricity and water. Individual step costs are derived by computing usage × rate; the printed total is used for validation. The water invoice may split steps across line breaks due to PDF extraction — the LLM prompt accounts for this.
- **LLM provider:** Groq API (free tier). Model: `llama-3.3-70b-versatile`. Can be swapped for Claude API later if accuracy is insufficient.
- **Connectivity:** pypdf runs offline; Groq API call requires internet. Acceptable — the user is explicitly uploading a PDF, implying connectivity.
- **No new frameworks** beyond `pypdf`, `groq`, and `python-dotenv`

---

## Key Decisions

1. **Parsing strategy:** pypdf extracts raw text; Groq LLM interprets it into structured JSON. Regex alone is insufficient because line items vary month to month and both invoice types pack multiple steps onto a single line.

2. **Data model:** One `coj_invoices` parent table with `invoice_type` column; one `coj_invoice_line_items` child table for variable rows. Avoids duplicating near-identical schemas for two invoice types.

3. **Step cost storage:** Store `usage_amount` and `rate` per step; compute cost as `usage × rate`. The printed combined total at the end of the step block is the validation target, not stored directly.

4. **Water invoice sections:** Property Rates and Refuse are normally R0.00 and not extracted. If non-zero (anomaly), they are captured as labelled fixed cost line items so validation still balances.

5. **Reading period dates:** Both start and end dates are captured — useful context for reconciliation with our own readings.

6. **Billing period columns:** `billing_year` and `billing_month` are stored on every invoice (one month behind the statement date — a March 2026 invoice covers February usage). This makes the future join to `meter_readings` explicit and avoids embedding the offset in every query.

7. **Meter number:** Stored in `ComplexSettings` as reference data, not on each invoice row. Validated against during parsing.

8. **Validation formula:** `sum(step costs) + sum(fixed charge costs) + total_vat ≈ total_due`, tolerance R0.10. This is one of six checks run on every parse.

9. **Auto-save on pass:** If all error-severity checks pass, the invoice is written to the DB and the PDF saved to `documents/invoices/` automatically. No manual confirm step required.

10. **Duplicate handling:** If a record already exists for that invoice type + statement month, a comparison UI is shown (existing vs. new) and Barry must explicitly choose to overwrite or keep the existing record. Pending parse data is held in a temp file during this flow.

---

## Validation Checks

All six checks run on every parse. The summary banner reflects the worst result.

| # | Check | Severity | Blocks save? |
|---|-------|----------|--------------|
| 1 | Invoice totals: steps + fixed + VAT ≈ total_due (±R0.10) | Error | Yes |
| 2 | Account number matches Complex Info | Error | Yes (skip if not configured) |
| 3 | Meter number matches Complex Info | Error | Yes (skip if not configured) |
| 4 | Consumption arithmetic: end_reading − start_reading = consumption | Error | Yes |
| 5 | Step usage sum: sum of step usage_amounts = consumption | Error | Yes |
| 6 | VAT rate: VAT ≈ 15% of pre-VAT total (±R1.00) | Warning | No |

If a reference value (account/meter number) is not yet configured in Complex Info, that check is skipped with a grey warning rather than failing.

---

## Data Model

### Table: `coj_invoices`

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| invoice_type | String | 'electricity' or 'water' |
| statement_year | Integer | e.g. 2026 |
| statement_month | Integer | 1–12 |
| billing_year | Integer | statement_month − 1 (year adjusted for January) |
| billing_month | Integer | statement_month − 1 (rolls to 12 for January) |
| invoice_date | Date | |
| invoice_number | String | |
| account_number | String | |
| payment_due_date | Date | |
| reading_period_start | Date | Start of CoJ billing read period |
| reading_period_end | Date | End of CoJ billing read period |
| start_reading | Numeric(12,4) | As printed on invoice |
| end_reading | Numeric(12,4) | As printed on invoice |
| consumption | Numeric(12,4) | As explicitly printed (kWh or KL) |
| total_vat | Numeric(10,2) | |
| total_due | Numeric(10,2) | |
| pdf_path | String | Relative path to saved PDF (e.g. `documents/invoices/electricity_2026_04.pdf`) |
| status | String | 'saved' |
| created_at | DateTime | |
| updated_at | DateTime | |

**Unique constraint:** `(invoice_type, statement_year, statement_month)`

**Note:** `meter_number` is intentionally absent — it is reference data stored in `ComplexSettings`, not per-invoice data.

### Table: `coj_invoice_line_items`

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| invoice_id | Integer FK → coj_invoices.id | Cascade delete |
| line_type | String | 'step' or 'fixed' |
| label | String | e.g. "Step 1", "Network Surcharge", "Sewer charge" |
| usage_amount | Numeric(12,4) | Steps only (kWh or KL) |
| rate | Numeric(10,6) | Steps only (R per unit) |
| cost | Numeric(10,2) | Fixed: as printed. Steps: usage × rate (computed) |
| sort_order | Integer | Preserves display order from invoice |

### Table: `complex_settings` (single-row reference data)

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | Always 1 |
| electricity_account_number | String | Expected CoJ City Power account number |
| electricity_meter_number | String | Expected City Power meter number |
| water_account_number | String | Expected Johannesburg Water account number |
| water_meter_number | String | Expected Johannesburg Water meter number |

---

## Invoice Structure Reference

### Electricity (City Power)

**Page 1 — Summary:**
- Date, Statement for, Invoice Number, Account Number, Payment Due Date
- Current Charges (Excl. VAT), VAT @ 15%, Total Due

**Page 2 — Detail:**
- Reading period (start date to end date, number of days)
- Meter number, start reading, end reading, consumption (kWh)
- Steps: single step per line when only one step; all steps on one line with a combined total when multiple, e.g. `Step 1 X kWh @ R Y  Step 2 X kWh @ R Y  ZZZ.ZZ`
- Fixed costs: Extended Social Package Grant, Network Surcharge, Service charge, Network charge (amounts may be R0.00)
- VAT line, Total

### Water & Sanitation (Johannesburg Water)

**Page 2 — Detail (3 sections):**
- **Property Rates** — normally R0.00; if non-zero, captured as anomalous fixed cost
- **Water & Sanitation:** reading period, meter number, start/end reading, consumption (KL), steps, fixed costs, VAT
- Steps: same single-line format as electricity — may split across line breaks in extracted text; prompt handles this
- Fixed costs: Extended Social Package Grant, Water Demand Levy, Sewer charge
- **Refuse** — normally R0.00; if non-zero, captured as anomalous fixed cost

---

## User Flow

1. Barry opens "CoJ Invoices" in the sidebar
2. Page shows the upload panel and, below it, the saved invoices history list
3. Barry selects invoice type and uploads PDF
4. A spinner shows while parsing (pypdf + Groq API call)
5. Results appear via HTMX partial swap (below the upload form):
   - **Saved banner** (indigo) — shown when all checks pass and data was written
   - **Validation summary banner** — green / yellow / red based on check results
   - **Individual checks list** — each check with pass/fail icon and message
   - **Invoice header** — date, invoice number, account number, due date, reading period, start/end reading, consumption
   - **Charges table** — steps (usage, rate, computed cost) then fixed charges; usage subtotal if >1 step
   - **Totals** — VAT, Total Due
   - **Database record panel** (open by default when saved) — shows exact rows written to `coj_invoices` and `coj_invoice_line_items`
   - **Debug panel** (collapsible) — raw text extracted by pypdf
6. If all error-severity checks pass: invoice is written to DB, PDF saved, "Saved to database" banner shown; the saved invoices list refreshes automatically via HTMX
7. If a duplicate exists: amber comparison panel shown with Overwrite / Keep existing buttons
8. Barry can click "Open" on any row in the saved invoices list to view the original PDF in a new browser tab

---

## Edge Cases

- **pypdf extracts garbled or minimal text** (image-based or corrupted PDF): error message + raw extracted text in debug panel
- **Groq API returns malformed JSON**: error with raw extracted text
- **Groq API unreachable**: clear network error
- **More than 4 steps**: handled — LLM extracts all regardless of count
- **New fixed cost label not seen before**: LLM captures it by label; included in validation automatically
- **Zero-value fixed cost line**: stored, shown in results in muted style
- **Validation rounding**: within R0.10 tolerance for totals check; within R1.00 for VAT rate warning
- **Water invoice anomalous sections**: non-zero Property Rates or Refuse captured as labelled anomaly fixed costs; yellow banner shown
- **Duplicate invoice**: comparison UI shown before any overwrite; temp file holds pending data during confirmation

---

## Risks

- **Groq LLM accuracy on complex water step line**: Multi-step water format packs all steps onto one line and may split across extracted text lines. Mitigation: prompt includes explicit example of broken-line format.
- **pypdf text quality**: Tables extract as runs of space-separated text. Mitigation: LLM prompt warns the model and instructs it to be robust to this.
- **Groq free tier rate limits**: ~2 parses per month — not a practical concern.
- **Format changes**: If CoJ changes invoice layout, extraction may break. Mitigation: debug panel shows raw text for immediate diagnosis.
