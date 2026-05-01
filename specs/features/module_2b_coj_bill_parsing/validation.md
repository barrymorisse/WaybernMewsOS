# validation.md — Module 2b: CoJ Bill Parsing

## Status: Complete ✅

---

## Functional Tests

- [x] PDF upload form works for electricity invoice type
- [x] PDF upload form works for water & sanitation invoice type
- [x] pypdf extracts readable text from a real CoJ electricity PDF
- [x] pypdf extracts readable text from a real CoJ water PDF
- [x] Groq API returns structured JSON with all expected fields for electricity invoice
- [x] Groq API returns structured JSON with all expected fields for water invoice
- [x] All extracted header fields display correctly (date, invoice number, account number, due date, reading period, start/end reading, consumption)
- [x] All step line items display correctly (label, usage, rate, computed cost)
- [x] All fixed charge line items display correctly (label, cost)
- [x] VAT and total due display correctly
- [x] All six validation checks run and display individually
- [x] Invoice totals check passes for correctly extracted electricity invoice
- [x] Invoice totals check passes for correctly extracted water invoice (within R0.10 tolerance)
- [x] Invoice totals check fails with correct discrepancy amount when amounts don't reconcile
- [x] Account number check passes when configured and matching
- [x] Account number check shows warning (not fail) when not yet configured
- [x] Meter number check passes when configured and matching
- [x] Meter number check shows warning (not fail) when not yet configured
- [x] Consumption arithmetic check passes (end − start = printed consumption)
- [x] Step usage sum check passes (sum of steps = consumption)
- [x] VAT rate check runs as warning-only
- [x] Invoice auto-saves to DB when all error checks pass
- [x] PDF saved to `documents/invoices/` with correct filename
- [x] Duplicate invoice shows comparison UI (existing vs. new)
- [x] Overwrite confirmed: old record deleted, new record written, PDF overwritten
- [x] Keep existing: temp file cleaned up, neutral message shown

---

## Edge Case Tests

- [x] Water invoice: all three steps extracted correctly from the single-line format (including line-break split)
- [x] Water invoice: Property Rates and Refuse sections not included in extracted results (both R0.00)
- [x] Zero-value fixed cost line (e.g. Extended Social Package Grant = R0.00) is shown but visually muted
- [x] Uploading a non-PDF file shows a clear error message
- [x] Groq API failure shows a clear error message, not a server crash
- [x] Malformed JSON from Groq shows error with raw text in debug panel

---

## UX Validation

- [x] Upload is a single action: choose type → select file → click upload
- [x] Results appear without a full page reload (HTMX partial swap)
- [x] Spinner visible while parsing is in progress
- [x] Validation summary banner is visually prominent (green / yellow / red)
- [x] Individual checks list shows each check with pass/fail icon and plain-English message
- [x] Debug panel is collapsible and does not dominate the page
- [x] Zero-value rows are included but visually de-emphasised (muted text)
- [x] DB record panel shows exact rows written, open by default when saved
- [x] Complex Info page allows account/meter numbers to be edited inline without page reload

---

## Invoice History & PDF Access

- [x] Saved invoices list displays on the CoJ Invoices page on initial load
- [x] List shows correct columns: type badge, statement month, billing period, invoice number, total due, save date, PDF link
- [x] List auto-refreshes after a successful save without a page reload (HTMX `invoiceSaved` trigger)
- [x] List auto-refreshes after an overwrite confirmation
- [x] PDF "Open" link appears for invoices that have a saved PDF
- [x] Clicking "Open" serves the PDF inline in a new browser tab
- [x] No PDF link shown (—) for invoices without a saved file
- [x] Empty state message shown when no invoices have been saved yet

## Data Integrity

- [x] `coj_invoices` table has correct columns (no `meter_number`)
- [x] `billing_year` and `billing_month` correctly computed (one month behind statement)
- [x] `coj_invoice_line_items` table has correct columns and FK to `coj_invoices.id`
- [x] `complex_settings` table has one row with electricity and water account/meter numbers
- [x] Unique constraint on `(invoice_type, statement_year, statement_month)` enforced
- [x] Cascade delete: deleting a `CojInvoice` removes all its line items

---

## April 2026 Reference Values (used for manual verification)

### Electricity Invoice

| Field | Expected Value |
|-------|---------------|
| Invoice date | 2026-04-02 |
| Statement month | April 2026 |
| Invoice number | 214000548251 |
| Account number | 220085271 |
| Payment due date | 2026-04-17 |
| Reading period | 2026-03-01 → 2026-03-31 |
| Meter number | 63030204 |
| Start reading | 543,123.000 kWh |
| End reading | 545,133.000 kWh |
| Consumption | 2,010.000 kWh |
| Step 1 | 2,010.000 kWh @ R2.5755 = R5,176.76 |
| Extended Social Package Grant | R0.00 |
| Network Surcharge | R0.00 |
| Service charge | R278.98 |
| Network charge | R1,125.75 |
| VAT | R987.22 |
| Total Due | R7,568.71 |
| billing_year / billing_month | 2026 / 3 |

### Water & Sanitation Invoice

| Field | Expected Value |
|-------|---------------|
| Invoice date | 2026-04-09 |
| Statement month | April 2026 |
| Invoice number | 22006872680 |
| Account number | 400744903 |
| Payment due date | 2026-04-30 |
| Reading period | 2026-02-22 → 2026-03-17 |
| Meter number | HJA1072 |
| Start reading | 10,324.000 KL |
| End reading | 10,364.000 KL |
| Consumption | 40.000 KL |
| Step 1 | 23.655 KL @ R0.0000 = R0.00 |
| Step 2 | 15.770 KL @ R29.840 = R470.59 |
| Step 3 | 0.575 KL @ R31.150 = R17.91 |
| Extended Social Package Grant | R0.00 |
| Water Demand Levy | R325.40 |
| Sewer charge | R3,488.65 |
| VAT | R645.38 |
| Total Due | R4,947.92 |
| billing_year / billing_month | 2026 / 3 |
