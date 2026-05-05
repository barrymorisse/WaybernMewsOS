# validation.md — Module 2c: Utility Consumption & Allocation

## Validation Criteria

### Functional Tests

- [ ] Auto-trigger fires correctly when all three inputs (elec invoice, water invoice, meter readings) are present for a billing month for the first time.
- [ ] Auto-trigger does NOT rerun if a calculation already exists for the billing month.
- [ ] `run_calculation()` correctly reads consumption from meter readings (current minus previous month).
- [ ] Common property electricity = max(0, elec_total − sum of unit 1–5 elec). Negative results clamped to zero.
- [ ] Common property water = max(0, water_total − sum of unit 1–5 water). Negative results clamped to zero.
- [ ] CoJ adjustment factor = CoJ consumption ÷ our total consumption (sum of 6 consumers). Full `Decimal` precision maintained.
- [ ] Adjusted figure per consumer = raw × adjustment factor (full precision). All 6 adjusted figures sum to CoJ consumption within 0.001.
- [ ] Step allocation handles any number of steps (1 through N) without hardcoding.
- [ ] Step allocation: within each step, usage is divided equally among consumers with remaining usage.
- [ ] Step allocation: a consumer who is exhausted (adjusted total < equal share) absorbs only their remaining usage; the shortfall is iteratively redistributed.
- [ ] Step allocation: a consumer with zero consumption absorbs zero usage at all steps.
- [ ] All step usage is fully allocated — no step finishes with unallocated usage (validated per step within 0.001).
- [ ] Fixed electricity costs: all fixed line items summed, divided by 5.
- [ ] Fixed water costs: all fixed line items **excluding** "Sewer charge" and its VAT (15%), divided by 5.
- [ ] Common property variable cost divided equally by 5 and added to each unit's bill.
- [ ] Per-unit total = variable cost + fixed share + common property share, all at 2dp.
- [ ] Rounding adjustment (if any) applied to Unit 1's variable cost; adjustment ≤ R0.10 before aborting.
- [ ] After rounding adjustment, sum of 5 unit electricity totals equals CoJ electricity `total_due` exactly.
- [ ] After rounding adjustment, sum of 5 unit water totals equals `CoJ water total_due − (sewer × 1.15)` exactly.
- [ ] Consumption and adjusted figures written to the new columns on the `meter_readings` row (full `Decimal` precision).
- [ ] All cost results saved to `billing_calculations`, `unit_billing_allocations`, and `billing_step_allocations` tables.
- [ ] No `float` arithmetic anywhere in the calculation service — `Decimal` exclusively.

---

### Edge Case Tests

- [ ] Previous month meter readings missing → calculation aborts with a clear error message; no partial data written to any table, including `meter_readings`.
- [ ] Negative raw consumption detected (meter rollover) → calculation aborts with a specific field-level error message.
- [ ] Common property is negative → clamped to zero, `common_property_clamped = True`, yellow warning shown on detail page; calculation proceeds normally.
- [ ] Adjustment factor outside 0.5–2.0 bounds → calculation aborts with descriptive error; no data written.
- [ ] A unit has zero consumption → treated as exhausted from the start of every step (adjusted figure = 0); absorbs zero variable cost; remaining step usage redistributed to remaining consumers.
- [ ] All units have zero consumption for a step (rate=0 free block) → step allocations recorded at R0 each; no divide-by-zero.
- [ ] Step 1 water has rate = 0 → step allocation runs correctly; all consumer costs at this step are R0.
- [ ] Month with only 1 step (electricity) → algorithm processes single step correctly with no errors.
- [ ] Month with 5 steps → algorithm iterates through all 5 steps correctly.
- [ ] Rounding adjustment > R0.10 → calculation aborts with error rather than silently applying a large correction.
- [ ] "Sewer charge" label absent from water invoice → logs a warning; no sewer excluded; notes field records the anomaly; calculation continues.
- [ ] Recalculate triggered on a period with an existing calculation → confirmation modal shown; on confirm: old `BillingCalculation`, all `UnitBillingAllocation`, all `BillingStepAllocation` rows deleted; derived `meter_readings` columns cleared; fresh calculation written.

---

### UX Validation

- [ ] List page shows all billing periods that have any CoJ invoice or meter reading data, sorted newest first.
- [ ] Status badges are clear: green "Calculated" with tick, grey "Pending", red "Reconciliation Error".
- [ ] Detail page sections flow in logical order (inputs → adjustment → steps → fixed → summary → reconciliation).
- [ ] Step allocation tables clearly show each consumer's adjusted total alongside their step allocation — Barry can see at a glance why a consumer absorbs less than the equal share at a step.
- [ ] Sewer charge is shown in the fixed costs section but clearly struck out or noted as excluded — transparency over hiding it.
- [ ] Reconciliation section shows the full arithmetic: CoJ total, sewer deduction (for water), billing target, our total, difference.
- [ ] Recalculate button triggers a confirmation modal — no accidental overwrites.
- [ ] Page loads in under 2 seconds even with multiple billing periods in the list.

---

### Data Integrity

- [ ] Only one `BillingCalculation` row per billing month (enforced by unique constraint).
- [ ] All `UnitBillingAllocation` rows are cascade-deleted when their parent `BillingCalculation` is deleted.
- [ ] All `BillingStepAllocation` rows are cascade-deleted when their parent `BillingCalculation` is deleted.
- [ ] When a calculation is deleted or overwritten, the derived columns on `meter_readings` are cleared (set to NULL) — no stale values left behind.
- [ ] No negative cost values stored in the database.
- [ ] Consumption and adjusted figures in `meter_readings` stored at full `Decimal` precision.
- [ ] Cost figures in `unit_billing_allocations` and `billing_calculations` stored at 2 decimal places.
- [ ] Adjustment factors in `billing_calculations` stored at 6 decimal places (Numeric 10,6).
- [ ] `Decimal` type used exclusively in the calculation service — no Python `float` arithmetic anywhere.

---

### Automation Check

- [ ] After saving a CoJ invoice for a billing month where all other data already exists, the calculation runs automatically without Barry visiting the Utility Billing page.
- [ ] After saving meter readings for a billing month where both CoJ invoices already exist, the calculation runs automatically.
- [ ] A failure in the auto-trigger does NOT cause the meter reading or CoJ invoice save to fail — errors are caught and logged.

---

## Manual Test Script

Follow these steps in sequence after the module is built to verify end-to-end behaviour.

### Setup: Confirm existing data

1. Open `http://localhost:8000/utility-billing`.
2. Confirm the page loads. If no calculations exist, it should show a list with "Pending" status for any months that have invoice or reading data.

### Test 1: Auto-trigger on meter reading entry

3. Navigate to Meter Readings. Identify a billing month that already has both CoJ invoices saved but no meter reading.
4. Enter and save meter readings for that month (including a previous month's reading if not already present — the system needs two consecutive months to compute consumption).
5. Navigate back to Utility Billing. Confirm the billing period now shows "Calculated" status.
6. Click through to the detail page.

### Test 2: Verify Section A — Inputs

7. Confirm the raw consumption figures shown match what you expect: e.g. if Unit 1's meter went from 1000 to 1100, its raw electricity consumption should show 100 kWh.
8. Confirm the CoJ invoice summary shows the correct invoice number and total due.

### Test 3: Verify Section B — Common Property

9. Manually calculate: `elec_total_raw − (unit1 + unit2 + unit3 + unit4 + unit5)`. Confirm the page shows the same figure.
10. Same for water.

### Test 4: Verify Section A — CoJ Adjustment

11. Confirm `our_total_elec = sum of 6 consumers' raw figures`.
12. Confirm `adjustment_factor = CoJ_consumption / our_total_elec` (use a calculator).
13. Confirm `adjusted_unit_1_elec = raw_unit_1_elec × adjustment_factor`.
14. Confirm `sum of all 6 adjusted figures = CoJ consumption` (should be exact within rounding tolerance).

### Test 5: Verify Section D/E — Step Allocation

15. For electricity Step 1: note the step kWh (e.g. 2010 kWh).
16. Divide by 6 = equal share per consumer. Confirm the first iteration of the algorithm allocates this equal share to each consumer (or less, if any consumer's adjusted total < equal share).
17. Sum all consumer allocations for this step. Confirm it equals the step kWh.
18. Multiply each consumer's step allocation by the step rate. Confirm it matches the cost shown.

### Test 6: Verify Section F — Fixed Costs

19. For electricity: sum all fixed line items manually. Confirm it matches the total shown. Divide by 5. Confirm the per-unit share.
20. For water: confirm "Sewer charge" is shown as excluded. Sum all other fixed line items. Confirm the total matches. Divide by 5.

### Test 7: Verify Section I — Reconciliation

21. Electricity: sum the 5 unit electricity totals shown in Section H. Confirm it equals CoJ electricity `total_due` within R0.01.
22. Water: compute `CoJ water total_due − (sewer_charge × 1.15)`. Confirm the 5 unit water totals sum to this figure within R0.01.
23. Both reconciliation rows should show green ticks.

### Test 8: Recalculate

24. Click "Recalculate". Confirm the confirmation modal appears with a warning.
25. Cancel. Confirm no change occurred.
26. Click "Recalculate" again. Confirm. Verify the calculation reruns and the page reloads with identical results (since no input data changed).

### Test 9: Verify meter_readings columns populated

27. After a successful calculation, run:
    ```
    sqlite3 data/waybern.db "SELECT elec_unit_1_consumption, elec_common_consumption, elec_unit_1_adjusted, elec_common_adjusted, water_unit_1_consumption, water_common_consumption FROM meter_readings WHERE year=XXXX AND month=XX;"
    ```
28. Confirm all 6 fields are populated with non-null 4dp values.
29. Confirm `elec_unit_1_consumption` matches the raw consumption figure and `elec_unit_1_adjusted` matches the adjusted consumption figure shown on the detail page.

### Test 10: Common property clamping (if testable)

30. Temporarily edit a meter reading so that `sum(unit readings)` > `total reading` (e.g. set total to a small value). Save.
31. Navigate to Utility Billing. Click Recalculate and confirm. Confirm the detail page shows a yellow warning about clamping.
32. Restore the correct reading, recalculate, confirm the warning disappears and the adjusted `meter_readings` columns show the correct (non-clamped) values.

### Test 11: Variable step count

33. Check the current invoice data — it has 1 electricity step and 3 water steps. Confirm both render correctly with the correct number of sub-tables in Section D.
34. Note: when future months have different step counts, this test should be repeated to confirm the algorithm and template handle them without code changes.
