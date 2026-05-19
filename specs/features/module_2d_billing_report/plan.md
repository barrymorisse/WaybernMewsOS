# plan.md — Billing Calculation Report (Module 2d)

## Implementation Summary

All tasks are complete. This document records what was built.

---

## Task Group 1 — Environment Setup ✅

- WeasyPrint installed via `pip install weasyprint` (v68.1).
- Added `weasyprint` to `requirements.txt`.
- Created `documents/utility_calculations/` directory.
- Added `documents/utility_calculations/*.pdf` to `.gitignore`.

---

## Task Group 2 — Data Layer ✅

Added to `BillingCalculation` in `app/models/billing.py`:
```python
pdf_path         = Column(String,   nullable=True)
pdf_generated_at = Column(DateTime, nullable=True)
```

Migration entry added to `_apply_migrations()` in `app/database.py`:
```python
("billing_calculations", "pdf_path",         "VARCHAR"),
("billing_calculations", "pdf_generated_at", "DATETIME"),
```

---

## Task Group 3 — Report Service ✅

Created `app/services/report_service.py`:

- `generate_billing_report(year, month, db) -> str | None`
  — public entry point; wraps `_generate()` with error handling, returns None on failure.
- `_generate(year, month, db) -> str`
  — loads all required data, renders `billing/report.html` via Jinja2,
  replaces `/static/` URL refs with `file://` absolute paths for WeasyPrint,
  writes PDF to `documents/utility_calculations/utility_calculation_{year}_{month:02d}.pdf`,
  updates `pdf_path` and `pdf_generated_at` on the `BillingCalculation` row,
  returns the PDF path.

Also exported from this module for use by the billing router:
- `group_steps(rows) -> list[dict]` — groups step allocation rows by step_number.
- `reading_rows(reading, prev_reading, prefix) -> list[dict]` — builds meter reading rows.

---

## Task Group 4 — Report Template ✅

`app/templates/billing/report.html` — standalone HTML document, no base.html inheritance.

Structure:
- Cover block (logo, org name, report title, period, generated timestamp)
- Section 1 — Electricity:
  1.1 Meter Readings (kWh)
  1.2 Step Cost Allocation (one sub-table per step)
  1.3 Fixed Charges
  1.4 Common Property Variable Cost
  1.5 Per-Unit Electricity Breakdown (with inline reconciliation row)
- Page break marker (dashed line visible on screen, hidden in print)
- Section 2 — Water (same 2.1–2.5 structure):
  - Step 1 shows Common Property as greyed/excluded (0 kL) with "(Units 1–5 only)" annotation
  - Fixed charges section shows sewer charge as greyed/excluded

All CSS embedded in `<style>` block. `@page { size: A4; margin: 18mm 20mm; }` for PDF layout.
Numbers formatted using the `fmt` Jinja2 filter (space as thousands separator).

---

## Task Group 5 — Trigger Integration ✅

`billing_service.run_calculation()` calls `report_service.generate_billing_report()` after
`db.commit()` and `db.refresh(calc)`:
```python
from app.services import report_service
report_service.generate_billing_report(billing_year, billing_month, db)
```

This covers both the auto-trigger path (`check_and_trigger()` → `run_calculation()`)
and the manual recalculate path (router POST → `run_calculation()`).

PDF generation failure is non-fatal: `generate_billing_report()` catches all exceptions,
logs the error, and returns None. The calculation record is preserved regardless.

---

## Task Group 6 — File Serving Route ✅

Added to `app/routers/billing.py`:
```
GET /utility-billing/{billing_year}/{billing_month}/report
```
Returns `FileResponse` with `media_type="application/pdf"` and
`Content-Disposition: inline` so it opens in the browser tab.
Returns a 404 HTML response if `pdf_path` is null or the file does not exist.

---

## Task Group 7 — UI Integration ✅

**`app/templates/billing/index.html`:**
- Added "Report" column with a red document SVG icon linking to the PDF route.
- Icon shown only when `calc.pdf_path` is populated; "—" shown otherwise.

**`app/templates/billing/detail.html`:**
- Added "Download Report (PDF)" button above the electricity/water links.
- Shows "Report not available" in dashed border when `pdf_path` is null.

**`app/templates/base.html`:**
- Removed temporary "Test: Report" amber sidebar link.
- Updated version footer to `v0.1 — Module 2d complete`.

---

## Task Group 8 — Cleanup ✅

- Removed `GET /utility-billing/report-preview` dev route from `app/routers/billing.py`.
- Removed `_reading_rows()` and `_group_steps()` private helpers from billing router
  (now live in `report_service.py`; billing router imports `group_steps` from there).
- Removed unused `datetime` and `groupby` imports from billing router.
