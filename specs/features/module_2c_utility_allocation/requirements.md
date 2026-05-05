# requirements.md — Module 2c: Utility Consumption & Allocation

## Overview

Module 2c takes the CoJ invoice data (parsed in Module 2b) and the monthly meter readings (entered in Module 2a) and produces a complete cost allocation for each of the 5 units. The output answers the question: "How much does each unit owe for electricity and water this month?"

The calculation runs automatically when all three required inputs are present for a billing month: the electricity invoice, the water invoice, and the meter readings. Results are stored in full and displayed with complete workings so Barry can verify every figure.

---

## Problem

The CoJ bills the complex as a whole. Barry needs to split that bill fairly across 5 units based on actual consumption. This currently requires manual spreadsheet work. The calculation involves several non-trivial steps (common property, CoJ adjustment, stepped tariff allocation) that are error-prone and time-consuming to do by hand.

---

## Goals

- Calculate each unit's share of the monthly electricity and water bill automatically.
- Store all intermediate figures (adjustment factors, step allocations, per-unit breakdowns) in the database.
- Display the full workings on screen so Barry can verify the logic at every step.
- Ensure the sum of all unit bills equals the CoJ invoice total exactly (within rounding tolerance of R0.01).
- Trigger automatically when all required data is present; allow manual recalculation with a warning.

---

## Non-Goals

- This module does **not** generate levy notices or send emails (that is Module 3).
- This module does **not** handle special levies or maintenance charges.
- This module does **not** allow Barry to override individual unit figures — it is a pure calculation.
- This module does **not** yet feed into Module 3 (levy billing). It stands alone and displays results for review.

---

## Constraints

- All figures must reconcile to the CoJ invoice total. For water, the reconciliation target is `total_due − (sewer_charge + sewer_VAT)` because sewerage is billed by CoJ but not split to units.
- Sewerage is identified by the label `"Sewer charge"` on the water invoice's fixed line items. Its VAT is computed as `sewer_charge × 0.15` (South African VAT rate).
- Common property consumption must never be negative. If `total_meter − sum(unit_1_to_5_meters)` yields a negative result (due to meter error or timing), it is clamped to zero and a warning is shown.
- The system must work offline. No LLM or external API calls are involved in this module.
- All intermediate calculations use Python's `Decimal` type (not float) to avoid floating-point rounding errors. Full `Decimal` precision is maintained throughout all intermediate steps — no intermediate rounding. Final ZAR billing figures are rounded to **2 decimal places** only at the point of display.
- The number of step line items per invoice is variable — some months may have 1 step, others up to 5 or more. The algorithm must handle any number of steps without hardcoding.

---

## Key Decisions

### Decision 1 — Common property as a 6th consumer in step allocation

Common property consumption is treated as a 6th consumer in the step-cost splitting algorithm (not handled separately). After step costs are allocated to all 6 consumers, common property's total variable cost is split equally across the 5 units. This is the fairest approach: each unit bears an equal share of the shared cost.

### Decision 2 — Step redistribution algorithm: iterative equal-split with proportional shortfall handling

Within each step, the available kWh/kL is divided equally among all consumers who still have remaining usage. If a consumer's total adjusted usage is less than their equal share at a step, they absorb only their remaining usage; the shortfall is iteratively redistributed among the remaining consumers by repeating the equal-split on the smaller remaining pool. This continues until the step is fully allocated. See the algorithm section below.

### Decision 3 — CoJ adjustment applied uniformly to all 6 consumers

The CoJ adjustment factor bridges the gap between our meter readings and the CoJ meter readings (which differ because CoJ reads on different dates). The factor is computed as `CoJ_consumption ÷ our_total_consumption`, where `our_total_consumption` is the sum of all 6 consumers (5 units + common property). It is applied uniformly to each consumer's raw usage. The adjusted figures are stored in the DB and are what the step allocation algorithm uses. The factor may be greater than 1 (CoJ read more than our meters) or less than 1 (CoJ read less) — "adjustment" is used in preference to "gross-up" since the direction is not fixed.

### Decision 4 — Auto-trigger with manual recalculate

Meter readings are always entered before invoices (CoJ invoices arrive one month in arrears, so readings are always the first input in). The auto-trigger therefore almost always fires when the second CoJ invoice is uploaded, not when readings are saved. The trigger logic checks for all three inputs regardless of order, but this expected sequence informs the UX: the Utility Billing page will typically show "Pending" while readings exist but invoices haven't arrived yet, then flip to "Calculated" when the second invoice is uploaded.

The calculation fires automatically the first time all three required inputs are present for a billing month. Subsequent recalculations (e.g. after a corrected meter reading or invoice) require Barry to click a "Recalculate" button and confirm a warning. This protects against accidental overwrites while keeping the workflow smooth.

### Decision 5 — Sewerage excluded from water billing

The CoJ water & sanitation invoice includes a "Sewer charge" fixed line item. This charge is **not** split to units — it is excluded entirely from the billing calculation. The reconciliation target for water is therefore `total_due_water − sewer_charge × 1.15`.

### Decision 6 — Step allocation uses adjusted figures, not raw readings

Raw meter consumption figures are stored for reference. All step-cost splitting uses adjusted figures so that the resulting costs, when summed, reconcile to the CoJ invoice total.

---

## Data Model Impact

### New table: `billing_calculations`

One row per billing period when a calculation has been run. This table stores the cost-split outputs and reconciliation results. Consumption figures (raw and adjusted) live in `meter_readings` — see below.

| Column | Type | Description |
|--------|------|-------------|
| id | Integer PK | |
| billing_year | Integer | |
| billing_month | Integer | |
| calculated_at | DateTime | When the calculation last ran |
| elec_adjustment_factor | Numeric(10,6) | CoJ elec consumption ÷ our total elec consumption |
| water_adjustment_factor | Numeric(10,6) | CoJ water consumption ÷ our total water consumption |
| elec_total_fixed_cost | Numeric(10,2) | Sum of all electricity fixed line items |
| water_total_fixed_cost | Numeric(10,2) | Sum of water fixed line items, **excluding** sewer and its VAT |
| elec_total_variable_cost | Numeric(10,2) | Sum of all electricity step costs (all 6 consumers) |
| water_total_variable_cost | Numeric(10,2) | Sum of all water step costs (all 6 consumers) |
| elec_common_variable_cost | Numeric(10,2) | Common property's share of electricity variable costs |
| water_common_variable_cost | Numeric(10,2) | Common property's share of water variable costs |
| elec_reconciliation_target | Numeric(10,2) | CoJ electricity total_due |
| water_reconciliation_target | Numeric(10,2) | CoJ water total_due minus sewer and sewer VAT |
| elec_units_total | Numeric(10,2) | Sum of all 5 unit electricity bills |
| water_units_total | Numeric(10,2) | Sum of all 5 unit water bills |
| elec_reconciled | Boolean | True if elec totals match within R0.01 |
| water_reconciled | Boolean | True if water totals match within R0.01 |
| common_property_clamped | Boolean | True if either common property figure was clamped to zero |
| notes | Text | Warnings, clamping notes, rounding adjustments |

Unique constraint: `(billing_year, billing_month)`.

---

### New table: `unit_billing_allocations`

Five rows per billing calculation (one per unit). Raw and adjusted consumption figures are not stored here — they live in `meter_readings`. This table stores cost outputs only.

| Column | Type | Description |
|--------|------|-------------|
| id | Integer PK | |
| billing_calculation_id | Integer FK → billing_calculations.id | |
| unit_number | Integer | 1–5 |
| elec_variable_cost | Numeric(10,2) | Unit's share of electricity step costs |
| water_variable_cost | Numeric(10,2) | Unit's share of water step costs |
| elec_fixed_share | Numeric(10,2) | Fixed electricity costs ÷ 5 |
| water_fixed_share | Numeric(10,2) | Fixed water costs ÷ 5 |
| elec_common_share | Numeric(10,2) | Common property electricity variable cost ÷ 5 |
| water_common_share | Numeric(10,2) | Common property water variable cost ÷ 5 |
| total_elec | Numeric(10,2) | elec_variable_cost + elec_fixed_share + elec_common_share |
| total_water | Numeric(10,2) | water_variable_cost + water_fixed_share + water_common_share |
| grand_total | Numeric(10,2) | total_elec + total_water |

---

### New table: `billing_step_allocations`

One row per consumer per step per invoice type. Used to render the step-by-step workings table in the UI.

| Column | Type | Description |
|--------|------|-------------|
| id | Integer PK | |
| billing_calculation_id | Integer FK → billing_calculations.id | |
| invoice_type | String | `'electricity'` or `'water'` |
| step_label | String | e.g. `'Step 1'` — from the line item label |
| step_number | Integer | Sort order |
| consumer_label | String | `'Unit 1'`…`'Unit 5'`, `'Common Property'` |
| adjusted_usage | Numeric(12,4) | Consumer's total adjusted usage (for reference) |
| usage_allocated | Numeric(12,4) | kWh or kL allocated to this consumer at this step |
| rate | Numeric(10,6) | Step tariff rate |
| cost | Numeric(10,2) | usage_allocated × rate |

---

### Modified table: `meter_readings` — new derived columns

Barry's intent is that `meter_readings` is the single source of truth for all consumption figures — both raw and processed. These columns are populated when the billing calculation runs and cleared if the calculation is deleted. They are nullable (no value until a calculation exists for that month).

Note: the existing columns in `meter_readings` store **cumulative** meter readings (the number on the dial). The new columns below store **consumption** figures (this month minus last month), plus the derived common property and adjusted values. They are a different type of data from the raw readings but belong on the same record because they describe the same month's activity.

**New columns to add to `meter_readings`:**

| Column | Type | Description |
|--------|------|-------------|
| elec_unit_1_consumption | Numeric(12,4) | Raw electricity consumption: current − previous reading |
| elec_unit_2_consumption | Numeric(12,4) | |
| elec_unit_3_consumption | Numeric(12,4) | |
| elec_unit_4_consumption | Numeric(12,4) | |
| elec_unit_5_consumption | Numeric(12,4) | |
| elec_common_consumption | Numeric(12,4) | max(0, elec_total_consumption − sum of unit consumptions) |
| elec_unit_1_adjusted | Numeric(12,4) | elec_unit_1_consumption × elec_adjustment_factor |
| elec_unit_2_adjusted | Numeric(12,4) | |
| elec_unit_3_adjusted | Numeric(12,4) | |
| elec_unit_4_adjusted | Numeric(12,4) | |
| elec_unit_5_adjusted | Numeric(12,4) | |
| elec_common_adjusted | Numeric(12,4) | elec_common_consumption × elec_adjustment_factor |
| water_unit_1_consumption | Numeric(12,4) | Raw water consumption: current − previous reading |
| water_unit_2_consumption | Numeric(12,4) | |
| water_unit_3_consumption | Numeric(12,4) | |
| water_unit_4_consumption | Numeric(12,4) | |
| water_unit_5_consumption | Numeric(12,4) | |
| water_common_consumption | Numeric(12,4) | max(0, water_total_consumption − sum of unit consumptions) |
| water_unit_1_adjusted | Numeric(12,4) | water_unit_1_consumption × water_adjustment_factor |
| water_unit_2_adjusted | Numeric(12,4) | |
| water_unit_3_adjusted | Numeric(12,4) | |
| water_unit_4_adjusted | Numeric(12,4) | |
| water_unit_5_adjusted | Numeric(12,4) | |
| water_common_adjusted | Numeric(12,4) | water_common_consumption × water_adjustment_factor |

`coj_invoices` and `coj_invoice_line_items` are read-only inputs to this module — no changes.

---

## The Calculation Algorithm

All arithmetic uses Python `Decimal` at full precision throughout — no intermediate rounding. Final ZAR figures are rounded to 2 decimal places only at the point of display. Consumption and adjusted figures are stored at full `Decimal` precision (SQLite stores whatever Python provides; the `Numeric(12,4)` type hint is for documentation only).

Each step below includes a **validation check** that must pass before proceeding. If a check fails, the calculation aborts, writes no data, and returns a descriptive error.

---

### Step 1 — Derive raw consumption

For each unit (1–5), subtract the previous month's meter reading from the current month's. Requires the previous month's `MeterReading` record to exist.

```
elec_unit_N_consumption = current_month.elec_unit_N − previous_month.elec_unit_N
water_unit_N_consumption = current_month.water_unit_N − previous_month.water_unit_N
elec_total_consumption = current_month.elec_total − previous_month.elec_total
water_total_consumption = current_month.water_total − previous_month.water_total
```

**Validation:** All consumption figures must be ≥ 0. A negative figure indicates a meter rollover or data entry error — abort with: *"Negative consumption detected for [field]. Check meter readings."*

**Validation:** Previous month `MeterReading` must exist — abort with: *"No prior month readings found for [month]. Cannot compute consumption."*

**Write:** Save consumption figures to the new `*_consumption` columns on the current month's `MeterReading` row.

---

### Step 2 — Compute common property raw consumption

```
elec_common_consumption = max(0, elec_total_consumption − sum(elec_unit_1…5_consumption))
water_common_consumption = max(0, water_total_consumption − sum(water_unit_1…5_consumption))
```

**Validation (soft):** If the unclamped value is negative, set `common_property_clamped = True` and add a warning to notes. Do not abort — clamp to zero and continue.

**Write:** Save `elec_common_consumption` and `water_common_consumption` to the current month's `MeterReading` row.

---

### Step 3 — Compute CoJ adjustment factors

```
our_total_elec = sum(elec_unit_1…5_consumption) + elec_common_consumption
our_total_water = sum(water_unit_1…5_consumption) + water_common_consumption

elec_adjustment_factor = CoJ_elec_invoice.consumption ÷ our_total_elec
water_adjustment_factor = CoJ_water_invoice.consumption ÷ our_total_water
```

**Validation:** `our_total_elec` and `our_total_water` must be > 0 — abort with: *"Total consumption is zero — cannot compute adjustment factor."*

**Validation:** Adjustment factors must be between 0.5 and 2.0 (i.e. within 50% of our readings). Outside this range is almost certainly a data error — abort with: *"Adjustment factor [X] is outside expected bounds (0.5–2.0). Check meter readings and CoJ invoice."*

---

### Step 4 — Apply adjustment factor to each consumer

```
For each of the 6 consumers (unit_1…unit_5, common_property):
    elec_adjusted = consumption × elec_adjustment_factor
    water_adjusted = consumption × water_adjustment_factor
```

**Validation:** Sum of all 6 adjusted electricity figures must equal `CoJ_elec_invoice.consumption` within 0.001 kWh. Same check for water. If not, abort — indicates a calculation error.

**Write:** Save all `elec_unit_N_adjusted`, `elec_common_adjusted`, `water_unit_N_adjusted`, and `water_common_adjusted` to the current month's `MeterReading` row.

---

### Step 5 — Allocate step costs

For each invoice type, iterate over **all** step line items (sorted by `sort_order`). The number of steps is variable — do not hardcode. Each step may have a rate of zero (e.g. the free indigent water allocation).

For each step:

```
remaining_step_usage = step.usage_amount
remaining_consumers = all 6 consumers           (each tracks remaining_usage = their full adjusted figure)

while remaining_step_usage > 0 and len(remaining_consumers) > 0:
    equal_share = remaining_step_usage / len(remaining_consumers)   (4dp)
    exhausted = []

    for consumer in remaining_consumers:
        if consumer.remaining_usage <= equal_share:
            # Consumer exhausted — absorbs only what they have left
            allocate(consumer, consumer.remaining_usage, step.rate)
            remaining_step_usage -= consumer.remaining_usage
            consumer.remaining_usage = 0
            exhausted.append(consumer)

    if not exhausted:
        # All remaining consumers absorb their equal share — step fully allocated
        for consumer in remaining_consumers:
            allocate(consumer, equal_share, step.rate)
            consumer.remaining_usage -= equal_share
        remaining_step_usage = 0
    else:
        for consumer in exhausted:
            remaining_consumers.remove(consumer)
        # Loop repeats — re-split remaining_step_usage among remaining consumers
```

`allocate(consumer, amount, rate)` records a `BillingStepAllocation` row and accumulates the consumer's variable cost (`amount × rate`).

`consumer.remaining_usage` tracks how much of the consumer's total adjusted usage has not yet been absorbed by previous steps.

**Validation after each step:** Sum of all 6 consumers' allocations for this step must equal `step.usage_amount` within 0.001. If not, abort — indicates algorithm error.

**Validation after all steps:** Sum of all consumers' allocations across all steps must equal CoJ invoice consumption within 0.01. If not, abort.

---

### Step 6 — Compute fixed cost splits

```
remaining_step_usage = step.usage_amount
remaining_consumers = all 6 consumers (copy of their adjusted_usage, tracking remaining_usage per consumer)

while remaining_step_usage > 0 and len(remaining_consumers) > 0:
    equal_share = remaining_step_usage / len(remaining_consumers)
    exhausted = []

    for consumer in remaining_consumers:
        if consumer.remaining_usage <= equal_share:
            # Consumer exhausted — they absorb all their remaining usage at this step
            allocate(consumer, consumer.remaining_usage, step.rate)
            remaining_step_usage -= consumer.remaining_usage
            consumer.remaining_usage = 0
            exhausted.append(consumer)

    if not exhausted:
        # All remaining consumers absorb their equal share
        for consumer in remaining_consumers:
            allocate(consumer, equal_share, step.rate)
            consumer.remaining_usage -= equal_share
        remaining_step_usage = 0
    else:
        for consumer in exhausted:
            remaining_consumers.remove(consumer)
```

Where `allocate(consumer, amount, rate)` records a `BillingStepAllocation` row and accumulates the consumer's variable cost.

Note: consumer.remaining_usage tracks how much of that consumer's total adjusted usage has not yet been absorbed by earlier steps. It starts at the full adjusted figure and decreases as steps are processed.

### Step 6 — Compute fixed cost splits

```
# Electricity
elec_fixed_total = sum(all electricity fixed line items)
elec_fixed_per_unit = elec_fixed_total / 5

# Water — identify and exclude sewer
sewer_line = first water fixed line item where label == "Sewer charge" (case-insensitive match)
if sewer_line not found:
    log warning: "No sewer charge found on water invoice — nothing excluded"
    sewer_cost = 0

water_fixed_total = sum(all water fixed line items) − sewer_line.cost
water_fixed_per_unit = water_fixed_total / 5
```

**Validation:** `elec_fixed_total + elec_total_variable_cost` must be close to (but may not exactly equal) `CoJ_elec_invoice.total_due` — a significant discrepancy (> R1) indicates a parsing problem; log a warning but do not abort.

---

### Step 7 — Common property cost split

```
elec_common_share_per_unit = elec_common_variable_cost / 5
water_common_share_per_unit = water_common_variable_cost / 5
```

**Validation:** `elec_common_variable_cost` must be ≥ 0. If somehow negative (algorithm error), abort.

---

### Step 8 — Compute per-unit totals

For each unit:
```
total_elec  = unit_elec_variable_cost + elec_fixed_per_unit + elec_common_share_per_unit
total_water = unit_water_variable_cost + water_fixed_per_unit + water_common_share_per_unit
grand_total = total_elec + total_water
```

**Validation:** All per-unit totals must be ≥ 0.

---

### Step 9 — Rounding adjustment

Rounding at 2dp during steps 6–8 may produce a small discrepancy (typically < R0.01) between the sum of unit bills and the reconciliation target. Apply the difference to Unit 1's variable cost to force exact reconciliation. Record the adjustment amount in the notes field.

```
elec_diff = elec_reconciliation_target − sum(unit.total_elec for all 5 units)
unit_1.elec_variable_cost += elec_diff   # small correction, positive or negative

water_diff = water_reconciliation_target − sum(unit.total_water for all 5 units)
unit_1.water_variable_cost += water_diff

Recompute unit_1.total_elec and unit_1.total_water after adjustment.
```

**Validation:** After adjustment, `|elec_diff|` and `|water_diff|` must each be ≤ R0.10. A larger discrepancy indicates a genuine calculation error — abort with: *"Rounding adjustment of R[X] exceeds tolerance. Check step allocation logic."*

---

### Step 10 — Reconciliation check

```
elec_units_total = sum(unit.total_elec for all 5 units)
water_units_total = sum(unit.total_water for all 5 units)

elec_reconciliation_target = CoJ_elec_invoice.total_due
water_reconciliation_target = CoJ_water_invoice.total_due − (sewer_line.cost × 1.15)

elec_reconciled = (elec_units_total == elec_reconciliation_target)   # exact after step 9
water_reconciled = (water_units_total == water_reconciliation_target) # exact after step 9
```

After the rounding adjustment in step 9, reconciliation should be exact. If it is not (which would indicate a logic error), the calculation is still saved but a prominent red error banner is shown on the detail page. Barry must investigate.

---

## User Flow

**Three-level navigation: list → overview → calculation detail**

1. Barry enters meter readings / saves a CoJ invoice → auto-trigger runs when all inputs are present.
2. Barry navigates to **Utility Billing** in the sidebar → sees the billing period list.
3. He clicks a billing period → the **overview page** for that month.
4. The overview page shows:
   - Status (calculated / pending / error)
   - A summary table: one row per unit, columns for Electricity charge and Water charge (no grand total column)
   - Two buttons: **"View Electricity Calculation"** and **"View Water Calculation"**
   - A secondary **"Recalculate"** button with confirmation modal
5. Barry clicks "View Electricity Calculation" → the **electricity detail page** showing:
   - Electricity meter readings and CoJ invoice inputs (raw consumption, CoJ adjustment factor, adjusted consumption)
   - Step cost allocation (electricity steps only)
   - Electricity fixed costs
   - Common property electricity cost split
   - Per-unit electricity summary (variable + fixed + common shares, total electricity per unit)
   - Electricity reconciliation check
6. He navigates back and clicks "View Water Calculation" → the **water detail page** showing the equivalent workings for water only, including the sewer exclusion logic.
7. If Barry spots an error:
   - He returns to the overview page and clicks **"Recalculate"**.
   - Confirmation modal warns: "This will overwrite the existing calculation for [Month Year]. Are you sure?"
   - On confirm, the calculation reruns and the page reloads.

---

## Edge Cases

| Scenario | Handling |
|----------|----------|
| Previous month's meter readings don't exist | Abort with error: "Cannot calculate — no prior month readings found to compute consumption." |
| Common property raw figure is negative | Clamp to zero, set `common_property_clamped = True`, show a yellow warning on the detail page. |
| A unit has zero consumption (vacant, no usage) | That consumer is removed from the step pool as soon as the step starts; they absorb R0 for variable costs. |
| All units have zero consumption for a step | Step cost of R0 is trivially allocated (rate=0 cases like Step 1 water). |
| Step 1 water has rate=0 (free indigent allocation) | Cost = 0 regardless of allocation. Algorithm handles this correctly since amount × 0 = 0. |
| Adjustment factor > 1 | Normal — CoJ read more usage than our meters. Figures are scaled up. |
| Adjustment factor < 1 | Normal — CoJ read less usage than our meters. Figures are scaled down. |
| Reconciliation fails (> R0.01 discrepancy) | Calculation is saved. Red banner shown on detail page. Barry must investigate — likely a data entry error. |
| Recalculate triggered after Module 3 has used this data | Not applicable yet (Module 3 not built). Note for future: Module 3 should lock the billing calculation once levies are raised. |
| Invoice has no step line items | Edge case not expected in practice; would result in zero variable costs. Fixed costs still split correctly. |

---

## Risks

| Risk | Mitigation |
|------|-----------|
| Floating-point rounding causes reconciliation failure | Use Python `Decimal` throughout; apply rounding adjustment to Unit 1 if needed. |
| "Sewer charge" label changes on future CoJ invoices | Detection by label is fragile. Log clearly if no sewer charge is found on the water invoice and default to excluding nothing. |
| Auto-trigger fires on stale/corrected invoice data | Auto-trigger only fires once (no existing calculation). Subsequent corrections require manual recalculate. |
| Previous month readings missing | Explicit error message. No silent failure. |
| User recalculates after Module 3 has raised levies | Future risk — noted for Module 3 spec. For now, recalculate is always available. |
