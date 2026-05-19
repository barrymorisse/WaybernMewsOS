# validation.md — Billing Calculation Report

## Validation Criteria

### Functional Tests

- [ ] PDF is generated automatically when all three inputs are present and the
      auto-trigger fires (no manual action required from Barry)
- [ ] PDF is regenerated automatically when "Recalculate" is triggered on the
      detail page
- [ ] Regenerated PDF overwrites the previous file cleanly (no orphaned files)
- [ ] `billing_calculations.pdf_path` is populated after generation
- [ ] `billing_calculations.pdf_generated_at` is populated after generation
- [ ] File exists at the path stored in `pdf_path`
- [ ] PDF is served inline in a new browser tab when the link is clicked (not
      forced as a download)
- [ ] PDF link appears on the billing list page
- [ ] "Download Report" button appears on the billing detail page
- [ ] If PDF generation fails (WeasyPrint error), the calculation result is NOT
      lost — it is still saved to the DB and the UI shows a "report not available"
      label rather than an error page

### Figures Accuracy

- [ ] Summary table (Section 1): unit totals match `unit_billing_allocations.grand_total`
- [ ] Electricity section: step allocation kWh and costs match `billing_step_allocations`
- [ ] Water section: step allocation kL and costs match `billing_step_allocations`
- [ ] Meter readings table: raw figures match `meter_readings`; consumption figures
      match `*_consumption` derived columns
- [ ] Adjusted consumption figures match `*_adjusted` derived columns on `meter_readings`
- [ ] CoJ adjustment factor matches `billing_calculations.elec_adjustment_factor` /
      `water_adjustment_factor`
- [ ] Fixed charges: figures match `coj_invoice_line_items` for the relevant invoice
- [ ] Reconciliation totals match `billing_calculations.elec_units_total` /
      `water_units_total` and their respective targets
- [ ] Sewer charge is shown as excluded in the water section and does not appear in
      any unit's water charge
- [ ] Common Property exclusion from water Step 1 is noted in the water step
      allocation section

### Readability (Manual Review)

- [ ] A person unfamiliar with the system can trace from a unit's grand total back
      through all contributing components without needing to refer to anything outside
      the report
- [ ] All section headings and column labels are plain English
- [ ] All intermediate steps are labelled with a brief explanation of what they represent
- [ ] Monetary values are formatted to 2 decimal places throughout
- [ ] Consumption figures are formatted to 4 decimal places throughout
- [ ] Factors are formatted to 4 decimal places throughout

### Layout & Presentation

- [ ] Report renders without WeasyPrint errors or warnings
- [ ] Tables do not break mid-row across page boundaries
- [ ] Cover block is clearly distinct from the calculation body
- [ ] All content is readable in print preview (black text, no background colours
      that print as grey)
- [ ] No external resources required — PDF renders offline

### Data Integrity

- [ ] Only one PDF file exists per billing month (regeneration overwrites, not appends)
- [ ] `documents/utility_calculations/` is listed in `.gitignore`
- [ ] PDF filename follows the convention `utility_calculation_{year}_{month:02d}.pdf`

---

## Manual Test Script

Follow these steps after implementation to confirm the feature is working end-to-end.

**Step 1 — Verify environment**
1. Open a terminal in the project directory.
2. Run `python -c "import weasyprint; print('ok')"` — confirm no import errors.

**Step 2 — Trigger generation via Recalculate**
1. Start the server (`./launch.sh`).
2. Navigate to a billing month that already has a calculation.
3. Click "Recalculate" and confirm in the modal.
4. After redirect, check the billing detail page — a "Download Report" button should
   be visible.
5. Click the button — the PDF should open in a new tab.

**Step 3 — Verify PDF contents**
Working through the open PDF:
1. Confirm the cover block shows the correct complex name, billing period, and
   generation timestamp.
2. In Section 1, add up the five unit grand totals manually. Check they match the
   "Total" row.
3. In Section 2 (Electricity), pick one unit. Trace: meter readings → consumption →
   adjusted consumption → step allocations → fixed share → common share → unit total.
   Confirm the arithmetic at each stage.
4. In Section 3 (Water), confirm the Step 1 table shows 0 kL for Common Property
   and a note explaining the free-water exclusion.
5. In Section 3, confirm the sewer charge is shown as excluded and does not appear
   in any unit's costs.
6. In Section 2 and 3, confirm the reconciliation rows show ✓ and that the sum of
   unit bills equals the CoJ target.

**Step 4 — Verify file storage**
1. In Finder, navigate to `documents/utility_calculations/`.
2. Confirm `utility_calculation_{year}_{month:02d}.pdf` exists.
3. Open it from Finder — should open correctly in Preview.

**Step 5 — Verify billing list page**
1. Navigate to `/utility-billing`.
2. Confirm the billing month tested above shows a PDF icon link.
3. Click the icon — same PDF opens in a new tab.

**Step 6 — Verify regeneration overwrites**
1. Note the file size of the existing PDF.
2. On the billing detail page, click Recalculate again.
3. Confirm only one file exists in `documents/utility_calculations/` for that month (not two).
4. Open the regenerated PDF — it should reflect the current calculation.

**Step 7 — Verify failure handling (optional)**
1. Temporarily uninstall WeasyPrint (`pip uninstall weasyprint`) or mock a failure.
2. Trigger a recalculation.
3. Confirm the calculation saves to DB correctly.
4. Confirm the billing detail page shows "Report not available" rather than an error.
5. Reinstall WeasyPrint.
