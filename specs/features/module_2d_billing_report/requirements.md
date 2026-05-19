# requirements.md — Billing Calculation Report (Module 2d)

## Overview

A PDF report that presents the full utility billing calculation for one month in a
clear, followable format. The report is generated automatically when all three inputs
(electricity invoice, water invoice, meter readings) are present and a calculation
runs. It is stored on disk and linked from the utility billing screen so it can be
downloaded at any time.

---

## Problem

The billing calculation is detailed and correct, but it lives only as a web UI that
requires login. A managing agent reviewing the figures, or an owner questioning their
bill, cannot be handed the working — there is no shareable, printable document that
shows how each unit's charge was derived.

---

## Goals

- Automatically produce a PDF showing the full workings for every billing month that
  has a completed calculation.
- Make the PDF accessible from the utility billing screen with one click.
- Regenerate the PDF automatically whenever the calculation is recalculated.
- Store PDFs persistently in `documents/utility_calculations/` alongside other complex records.
- Present calculations clearly enough that a managing agent or owner with no knowledge
  of the system can follow every step from meter reading to final charge.

---

## Non-Goals

- No manual "generate" button — generation is fully automatic.
- No email dispatch (that is Module 6 scope).
- No multi-month or annual summary report (one PDF per billing month).
- No password protection or watermarking.
- No Excel output.

---

## Constraints

- Uses WeasyPrint (HTML → PDF). Installed via `pip install weasyprint`.
- PDF generation runs synchronously after the calculation commits, before the response
  is returned. Acceptable given the small data volumes involved.
- `documents/utility_calculations/` must be gitignored (same policy as invoices and insurance).
- The PDF must be fully self-contained: no external fonts or resources that require
  internet access to render.

---

## Key Decisions

**PDF, not Excel.**
The purpose is a formal, shareable audit record. PDF is non-editable, printable, and
appropriate for disputes and year-end filing.

**Auto-generation, not on-demand.**
Tying generation to the calculation run (both auto-trigger and manual recalculate paths)
ensures the stored PDF always matches the DB figures.

**Store path on `billing_calculations`.**
`pdf_path` and `pdf_generated_at` on `billing_calculations` keeps the link obvious.

**WeasyPrint HTML template, not a library like ReportLab.**
The rest of the app uses Jinja2 HTML templates. The report is designed in HTML/CSS —
consistent tooling, maintainable layout.

**Full workings, not a summary.**
Every intermediate value (raw consumption, adjustment factor, per-step allocation,
fixed cost split, rounding) is shown and labelled.

---

## Data Model Impact

**`billing_calculations` table — two new columns:**
- `pdf_path` (String, nullable) — absolute path to the generated PDF on disk.
  Null until the first PDF is generated for that row.
- `pdf_generated_at` (DateTime, nullable) — timestamp of last PDF generation.

**New directory:**
- `documents/utility_calculations/` — created on first use; gitignored.

**Filename convention:**
- `utility_calculation_{year}_{month:02d}.pdf` — e.g. `utility_calculation_2026_04.pdf`
- Deterministic name means a regenerated report overwrites the previous file cleanly.

No other schema changes. All data needed for the report already exists in the three
billing tables and in `meter_readings` / `coj_invoice_line_items`.

---

## Report Structure

The report is a standalone HTML document (no base.html inheritance — print-oriented
layout without the app sidebar). WeasyPrint handles pagination automatically.

### Cover block
- Waybern Mews logo + "Waybern Mews Body Corporate"
- "Utility Billing Calculation"
- Billing period: e.g. "April 2026"
- Generated date and time

### Section 1 — Electricity

**1.1 Meter Readings (kWh)**
Table: Unit | Previous Reading | Current Reading | Raw Consumption | Adjusted Consumption
- Rows: Unit 1–5, Common Property
- Bold Total row; blue CoJ Consumption row (invoice figure for reference)

**1.2 Step Cost Allocation**
For each tariff step (one sub-table per step):
- Step label and rate (R/kWh)
- Table: Unit | Total Adjusted (kWh) | Allocated to Step (kWh) | Cost ex-VAT (R)
- Bold "Our total" row; blue "CoJ Step Total" row with step usage and cost from invoice

**1.3 Fixed Charges**
Table: Charge | Amount ex-VAT (R)
- Zero-cost items suppressed. Total and per-unit (÷ 5) rows.

**1.4 Common Property Variable Cost**
Total variable cost allocated to Common Property (R); per-unit split (÷ 5).

**1.5 Per-Unit Electricity Breakdown**
Table: Unit | Variable Cost | Fixed Share | Common Share | Total Electricity (R)
- Includes inline CoJ target reconciliation row with ✓ / ✗ badge.

### Section 2 — Water

Same structure (2.1–2.5) with two differences:
- **Step 1 table** shows Common Property as greyed-out with 0 kL (excluded from free
  water allowance) and a green annotation "(Units 1–5 only)" next to the step heading.
- **2.3 Fixed Charges** shows the sewer charge line in grey as "(excluded — bulk account
  cost)", and the billable total excludes it.

---

## User Flow

1. Barry uploads both CoJ invoices and enters meter readings for a billing month.
2. The existing `check_and_trigger()` logic fires the calculation automatically.
3. `billing_service.run_calculation()` calls `report_service.generate_billing_report()`
   after the calculation commits.
4. PDF saved to `documents/utility_calculations/utility_calculation_{year}_{month:02d}.pdf`.
5. `pdf_path` and `pdf_generated_at` written to `billing_calculations`.
6. The utility billing list page shows a red document icon next to any month with a report.
7. Clicking opens the PDF inline in a new browser tab.
8. The billing detail page shows a "Download Report (PDF)" button.
9. If Barry hits "Recalculate", the calculation reruns and the PDF is regenerated.

---

## Edge Cases

- **WeasyPrint failure:** PDF generation fails gracefully — the calculation still saves,
  `pdf_path` remains null, error is logged. Detail page shows "Report not available".
- **`documents/utility_calculations/` missing:** Created automatically on first write.
- **Recalculate overwrites existing PDF:** Intentional — PDF always reflects current calculation.
- **Null meter reading fields:** Consumption cells show "—" rather than crashing.
- **Common property clamped to zero:** Shown in the meter readings table; a note appears
  in `billing_calculations.notes` (accessible via the calculation notes panel on the detail page).
