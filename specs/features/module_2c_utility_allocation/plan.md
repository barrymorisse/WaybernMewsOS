# plan.md — Module 2c: Utility Consumption & Allocation

## Plan

---

### Task Group 1 — Data Layer

**1.1** Extend `app/models/meter_readings.py` — add 24 new nullable columns to `MeterReading`:

Consumption columns (derived from current − previous reading):
- `elec_unit_1_consumption` through `elec_unit_5_consumption` (Numeric 12,4)
- `elec_common_consumption` (Numeric 12,4)
- `water_unit_1_consumption` through `water_unit_5_consumption` (Numeric 12,4)
- `water_common_consumption` (Numeric 12,4)

Adjusted columns (consumption × CoJ adjustment factor):
- `elec_unit_1_adjusted` through `elec_unit_5_adjusted` (Numeric 12,4)
- `elec_common_adjusted` (Numeric 12,4)
- `water_unit_1_adjusted` through `water_unit_5_adjusted` (Numeric 12,4)
- `water_common_adjusted` (Numeric 12,4)

All new columns use `Column(Numeric(12, 4), nullable=True)`. SQLAlchemy will add them on next startup via `create_all()` — no Alembic migration needed (SQLite, dev environment).

**1.2** Create `app/models/billing.py` with three SQLAlchemy models:
- `BillingCalculation` (maps to `billing_calculations` table) — cost totals, CoJ adjustment factors, reconciliation results
- `UnitBillingAllocation` (maps to `unit_billing_allocations` table) — cost breakdown per unit (no consumption data, that lives in `meter_readings`)
- `BillingStepAllocation` (maps to `billing_step_allocations` table) — per consumer per step, for displaying workings

Include relationships: `BillingCalculation` → `unit_allocations` (one-to-many) and → `step_allocations` (one-to-many), both with `cascade="all, delete-orphan"`.

**1.3** Register the new models in `app/models/__init__.py` so `Base.metadata.create_all()` picks them up on next startup.

**1.4** Start the app and verify all new tables and columns exist:
```
sqlite3 data/waybern.db ".tables"
sqlite3 data/waybern.db "PRAGMA table_info(meter_readings);"
sqlite3 data/waybern.db "PRAGMA table_info(billing_calculations);"
```

---

### Task Group 2 — Calculation Service

**2.1** Create `app/services/billing_service.py`. All calculation logic lives here — no business logic in the router. Use Python's `Decimal` type throughout at full precision — no intermediate rounding. Round final ZAR cost figures to 2 decimal places only at the point of display.

The file should contain the following functions:

---

**`check_and_trigger(billing_year, billing_month, db) → str`**
- Checks whether both CoJ invoices (electricity + water) and a `MeterReading` exist for the given `billing_year` + `billing_month`.
- If all present and no `BillingCalculation` exists for that month: calls `run_calculation()` and returns `"triggered"`.
- If all present but calculation already exists: returns `"already_exists"`.
- If data is incomplete: returns `"not_ready"`.

---

**`run_calculation(billing_year, billing_month, db) → BillingCalculation`**
- Orchestrates all 10 algorithm steps from requirements.md in sequence.
- Before writing any results, deletes any existing `BillingCalculation` (and cascade-deleted child rows) for this period, and clears the derived columns on the `MeterReading` row.
- On any `ValueError` from a validation check: rolls back, writes nothing, re-raises.
- On success: writes all results to DB and returns the `BillingCalculation` object.

---

**`_derive_raw_consumption(current: MeterReading, previous: MeterReading) → dict`**
- Computes `current.elec_unit_N − previous.elec_unit_N` for each of the 5 units plus total (electricity and water).
- Validates all results are ≥ 0 (raises `ValueError` if negative).
- Returns a dict with keys `elec_unit_1` … `elec_unit_5`, `elec_total`, `water_unit_1` … `water_unit_5`, `water_total`.
- All values as `Decimal`, 4dp.

---

**`_compute_common_property(raw: dict) → tuple[Decimal, Decimal, bool]`**
- `elec_common = max(0, raw['elec_total'] − sum(raw['elec_unit_1'…5]))`
- `water_common = max(0, raw['water_total'] − sum(raw['water_unit_1'…5]))`
- Returns `(elec_common, water_common, clamped)` where `clamped = True` if either value was negative before clamping.

---

**`_compute_adjustment_factors(raw: dict, elec_common: Decimal, water_common: Decimal, coj_elec: CojInvoice, coj_water: CojInvoice) → tuple[Decimal, Decimal]`**
- `our_total_elec = sum(unit consumptions) + elec_common`
- `our_total_water = sum(unit consumptions) + water_common`
- Validates both totals > 0 (raises `ValueError` if zero).
- `elec_factor = Decimal(coj_elec.consumption) / our_total_elec` (full precision)
- `water_factor = Decimal(coj_water.consumption) / our_total_water` (full precision)
- Validates both factors are between 0.5 and 2.0 (raises `ValueError` if outside bounds).
- Returns `(elec_factor, water_factor)`.

---

**`_apply_adjustment(raw: dict, elec_common: Decimal, water_common: Decimal, elec_factor: Decimal, water_factor: Decimal) → dict`**
- For each of the 6 consumers: `adjusted = raw_consumption × factor` (full precision).
- Validates that sum of all 6 adjusted electricity figures equals CoJ electricity consumption within 0.001 kWh (raises `ValueError` if not).
- Same check for water.
- Returns dict with keys `elec_unit_1_adjusted` … `elec_unit_5_adjusted`, `elec_common_adjusted`, and water equivalents.

---

**`_allocate_steps(step_items: list[CojInvoiceLineItem], adjusted: dict, invoice_type: str) → tuple[list[dict], dict[str, Decimal]]`**

Implements the iterative equal-split step allocation algorithm. Works for any number of steps.

```
consumers = {
    'Unit 1': adjusted[f'{invoice_type}_unit_1_adjusted'],
    'Unit 2': ...,
    'Unit 3': ...,
    'Unit 4': ...,
    'Unit 5': ...,
    'Common Property': adjusted[f'{invoice_type}_common_adjusted'],
}
# remaining_usage[consumer] starts at their full adjusted figure and decreases across steps

step_allocation_rows = []    # one dict per consumer per step → becomes BillingStepAllocation rows
variable_costs = defaultdict(Decimal)   # accumulates cost per consumer across all steps

for step in step_items:  # already sorted by sort_order
    remaining_step = Decimal(step.usage_amount)
    remaining_consumers = {c: remaining_usage[c] for c in remaining_usage if remaining_usage[c] > 0}

    while remaining_step > 0 and remaining_consumers:
        equal_share = remaining_step / len(remaining_consumers)
        exhausted = {}

        for consumer, usage_left in remaining_consumers.items():
            if usage_left <= equal_share:
                exhausted[consumer] = usage_left

        if not exhausted:
            for consumer in remaining_consumers:
                allocate(consumer, equal_share, step)
                remaining_usage[consumer] -= equal_share
            remaining_step = 0
        else:
            for consumer, used in exhausted.items():
                allocate(consumer, used, step)
                remaining_usage[consumer] = 0
                remaining_step -= used
                del remaining_consumers[consumer]

    # Validation: sum of allocations for this step must equal step.usage_amount within 0.001
    step_total = sum(row['usage_allocated'] for row in this_step_rows)
    if abs(step_total - Decimal(step.usage_amount)) > Decimal('0.001'):
        raise ValueError(f"Step allocation error: {step.label} allocated {step_total}, expected {step.usage_amount}")

# Validation: sum of all allocations must equal CoJ consumption within 0.01
total_allocated = sum(variable_costs.values() / step.rate for all steps)  # check usage not cost
```

`allocate(consumer, amount, step)` appends a dict to `step_allocation_rows` and adds `amount × Decimal(step.rate)` to `variable_costs[consumer]`.

Returns `(step_allocation_rows, variable_costs)`.

---

**`_compute_fixed_costs(fixed_items: list[CojInvoiceLineItem], invoice_type: str) → tuple[Decimal, Decimal]`**
- For `invoice_type == 'electricity'`: sum all fixed line items. Return `(total, Decimal(0))`.
- For `invoice_type == 'water'`: find the line item where `label.lower() == 'sewer charge'`. If found: `sewer_ex_vat = item.cost`, `sewer_incl_vat = sewer_ex_vat × 1.15`. If not found: log warning, `sewer_incl_vat = 0`. Return `(total_excluding_sewer, sewer_incl_vat)`.

---

**`_apply_rounding_adjustment(unit_costs: dict, elec_target: Decimal, water_target: Decimal, notes: list[str]) → dict`**
- Computes `elec_diff = elec_target − sum(unit_costs[n]['total_elec'] for n in 1..5)`.
- If `|elec_diff| > Decimal('0.10')`: raises `ValueError` — adjustment exceeds tolerance.
- Applies `elec_diff` to Unit 1's `elec_variable_cost`. Recomputes Unit 1's `total_elec` and `grand_total`.
- Same for water.
- Appends adjustment amount to `notes` if non-zero.
- Returns updated `unit_costs`.

---

**2.2** All functions that perform arithmetic must use `Decimal` values exclusively. No mixing of `float` and `Decimal`. Convert any `Numeric` values from the DB with `Decimal(str(value))` before use. No intermediate `quantize()` calls — full precision is carried throughout, only formatted for display in templates.

**2.3** Each private function must have a docstring explaining its inputs, outputs, and what it validates.

---

### Task Group 3 — Auto-Trigger Wiring

**3.1** In `app/routers/meter_readings.py`: after a meter reading is successfully committed to the DB, add:
```python
try:
    result = billing_service.check_and_trigger(reading.year, reading.month, db)
    print(f"[billing] trigger result for {reading.year}-{reading.month:02d}: {result}")
except Exception as e:
    print(f"[billing] auto-trigger failed for {reading.year}-{reading.month:02d}: {e}")
```
This must not raise — the meter reading save must succeed regardless of billing status.

**3.2** In `app/routers/coj_invoices.py`: same pattern after a CoJ invoice is saved, using `invoice.billing_year` and `invoice.billing_month`.

Note: in normal operation, meter readings are saved first (readings come before the invoices). The trigger will fire when the second invoice is uploaded. Both hooks are wired for robustness.

---

### Task Group 4 — Router

**4.1** `app/routers/billing.py` routes:

**`GET /utility-billing`** — list page
- Query all unique `(billing_year, billing_month)` pairs from both `coj_invoices` and `meter_readings`.
- Left-join each pair to `billing_calculations`. Sort newest first.
- Pass to `billing/index.html`.

**`GET /utility-billing/{billing_year}/{billing_month}`** — overview page
- Load `BillingCalculation` with eager-loaded `unit_allocations`.
- Load both `CojInvoice` records and the current month's `MeterReading`.
- Pass to `billing/detail.html` (the overview — summary table + two "View" buttons).

**`GET /utility-billing/{billing_year}/{billing_month}/electricity`** — electricity detail
- Load full calculation data (step allocations, reading, elec invoice line items).
- Pass to `billing/electricity.html`.

**`GET /utility-billing/{billing_year}/{billing_month}/water`** — water detail
- Load full calculation data (step allocations, reading, water invoice line items, sewer charge).
- Pass to `billing/water.html`.

**`GET /utility-billing/{billing_year}/{billing_month}/recalc-modal`** — modal partial
**`POST /utility-billing/{billing_year}/{billing_month}/recalculate`** — recalculate
- On success: HX-Redirect to the overview page.

**4.2** Register in `main.py`:
```python
from app.routers import billing
app.include_router(billing.router)
```

---

### Task Group 5 — Templates

**5.1** `billing/index.html` — list page (unchanged from original)

Table columns: Billing period, Status badge, Total electricity, Total water, View link. No grand total column.

---

**5.2** `billing/detail.html` — overview page (replaces the combined detail)

Shows:
- Status badge + clamping warning if applicable
- Summary table: rows = units 1–5, columns = Electricity charge | Water charge (no grand total column)
- Two prominent buttons: "View Electricity Calculation →" and "View Water Calculation →"
- Secondary "Recalculate" button with confirmation modal
- "Not yet calculated" state if no calculation exists

---

**5.3** `billing/electricity.html` — electricity workings

Breadcrumb: Utility Billing → March 2026 → Electricity

Sections (electricity-only):
- **A** — Electricity meter readings (current vs previous, units 1–5 + total) + CoJ electricity invoice summary
- **B** — Common property electricity (total − sum of units, clamping warning if applicable)
- **A** — Electricity meter readings + CoJ adjustment (combined table: raw consumption, adjustment factor, adjusted consumption per consumer)
- **D** — Step cost allocation (one sub-table per step, any number of steps)
- **E** — Electricity fixed costs (line items, total, ÷5 per unit)
- **F** — Common property electricity cost split (total ÷ 5 per unit)
- **G** — Per-unit electricity summary (variable + fixed + common = total electricity per unit)
- **H** — Electricity reconciliation (sum of unit bills vs CoJ total_due, VAT factor shown)

"← Back to overview" link at top and bottom.

---

**5.4** `billing/water.html` — water workings

Same structure as electricity.html but for water, with these differences:
- Sewer charge shown in fixed costs section with strikethrough and "(excluded)" label
- Sewer VAT deduction shown explicitly in reconciliation
- Reconciliation target = CoJ water total_due − sewer_incl_vat

"← Back to overview" link at top and bottom.

**Section H — Reconciliation**

Two rows:

Electricity:
`Sum of unit bills: R X,XXX.XX | CoJ invoice total: R X,XXX.XX | ✓ Reconciled` (green)
or `✗ Discrepancy: R X.XX` (red banner)

Water:
`Sum of unit bills: R X,XXX.XX`
`CoJ water total due: R X,XXX.XX`
`Less: Sewer charge (ex. VAT): R X,XXX.XX`
`Less: Sewer VAT (15%): R XXX.XX`
`= Billing target: R X,XXX.XX`
`✓ Reconciled` or `✗ Discrepancy: R X.XX`

If notes field is non-empty (e.g. rounding adjustment or clamping), show it as a grey info box beneath reconciliation.

**Recalculate button**: bottom of page. Grey/secondary styling. On click: HTMX triggers a confirmation modal overlay. On confirm: POST to `/utility-billing/{year}/{month}/recalculate`.

If no calculation exists: show a "Not yet calculated" info panel with explanation of what's still missing (which of the three inputs is absent).

---

**5.3** Add "Utility Billing" to the sidebar nav in `base.html`, below "CoJ Invoices".

---

### Task Group 6 — Integration & Testing

**6.1** Start the app. Confirm `/utility-billing` loads with no errors when no billing data exists.

**6.2** Confirm the sidebar link appears and navigates correctly.

**6.3** Using the existing data in the DB (one electricity invoice already saved), navigate to the billing list. Confirm the relevant billing period appears as "Pending".

**6.4** Enter and save meter readings for that billing period (ensuring a previous month's reading also exists). Confirm the auto-trigger fires but returns `"not_ready"` (second invoice not yet present).

**6.5** Upload the second CoJ invoice (water) for the same billing period. Confirm the auto-trigger fires and the calculation runs. Navigate to the detail page. Confirm all sections render.

**6.6** Verify each section's figures manually:
- Raw consumption (current − previous) matches what you'd calculate by hand.
- Common property = total − sum of units.
- CoJ adjustment factor = CoJ consumption ÷ our total.
- Adjusted figures sum to CoJ consumption.
- Step allocations sum correctly per step.
- Fixed cost per unit = total fixed ÷ 5.
- Sewer charge is shown as excluded.
- Reconciliation shows green ticks.

**6.7** Test the Recalculate flow: click Recalculate, confirm modal appears, cancel (no change), confirm again (calculation reruns, page reloads with same results).

**6.8** Test the clamping warning: temporarily edit a meter reading so `elec_total` < sum of unit readings. Save. Recalculate. Confirm yellow warning appears. Restore correct reading, recalculate, confirm warning gone.

**6.9** Verify the new `meter_readings` columns were populated after the calculation: `sqlite3 data/waybern.db "SELECT elec_unit_1_consumption, elec_common_consumption, elec_unit_1_adjusted, water_common_adjusted FROM meter_readings WHERE year=XXXX AND month=XX;"`
