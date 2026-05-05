"""
Service layer for Module 2c: Utility Consumption & Allocation.

All billing calculation logic lives here. The router calls check_and_trigger()
or run_calculation() — no arithmetic happens in the router.

Precision rules:
  - All arithmetic uses Python Decimal throughout (never float).
  - No rounding is applied to intermediate values — full Decimal precision is
    carried through the entire calculation pipeline.
  - SQLite stores whatever precision Python provides (NUMERIC type affinity
    does not enforce scale in SQLite).
  - Rounding for display is handled exclusively in the templates.
  - The one exception is the rounding adjustment (Step 9), which adds the
    exact difference needed to make the sum of unit bills equal the CoJ target
    to the cent, preserving reconciliation integrity.

Consumers in the step allocation:
  There are 6 consumers per invoice type: Unit 1–5 plus Common Property.
  After step costs are allocated, Common Property's variable cost is split
  equally across the 5 units.
"""

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy.orm import Session

from app.models.billing import (
    BillingCalculation,
    BillingStepAllocation,
    UnitBillingAllocation,
)
from app.models.coj_invoice import CojInvoice, CojInvoiceLineItem
from app.models.meter_readings import MeterReading

# Used only for the rounding adjustment (step 9) and DB-boundary formatting.
TWO_DP  = Decimal("0.01")
FOUR_DP = Decimal("0.0001")
SIX_DP  = Decimal("0.000001")

# All 6 consumer labels in a fixed order
CONSUMER_LABELS = ["Unit 1", "Unit 2", "Unit 3", "Unit 4", "Unit 5", "Common Property"]
UNIT_LABELS     = [f"Unit {n}" for n in range(1, 6)]

# CoJ adjustment factor sanity bounds — a factor outside this range almost certainly means bad data
ADJ_FACTOR_MIN = Decimal("0.5")
ADJ_FACTOR_MAX = Decimal("2.0")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_and_trigger(billing_year: int, billing_month: int, db: Session) -> str:
    """
    Check whether all three inputs are present for this billing month and, if so,
    run the calculation for the first time.

    Returns:
        "triggered"      — calculation ran successfully for the first time
        "already_exists" — calculation already exists; no action taken
        "not_ready"      — one or more inputs are missing
    """
    elec_inv  = _get_invoice(db, billing_year, billing_month, "electricity")
    water_inv = _get_invoice(db, billing_year, billing_month, "water")
    reading   = _get_reading(db, billing_year, billing_month)

    if not (elec_inv and water_inv and reading):
        return "not_ready"

    existing = (
        db.query(BillingCalculation)
        .filter_by(billing_year=billing_year, billing_month=billing_month)
        .first()
    )
    if existing:
        return "already_exists"

    run_calculation(billing_year, billing_month, db)
    return "triggered"


def run_calculation(billing_year: int, billing_month: int, db: Session) -> BillingCalculation:
    """
    Execute the full 10-step billing calculation for the given billing month.

    Deletes any existing BillingCalculation (and cascade-deleted children) and
    clears the derived columns on the MeterReading row before writing fresh results.

    Raises ValueError with a descriptive message if any validation check fails.
    All-or-nothing: on failure, no data is written.
    """
    # --- Gather inputs ---
    elec_inv  = _get_invoice(db, billing_year, billing_month, "electricity")
    water_inv = _get_invoice(db, billing_year, billing_month, "water")
    reading   = _get_reading(db, billing_year, billing_month)

    if not elec_inv:
        raise ValueError(f"No electricity invoice found for billing period {billing_year}-{billing_month:02d}.")
    if not water_inv:
        raise ValueError(f"No water invoice found for billing period {billing_year}-{billing_month:02d}.")
    if not reading:
        raise ValueError(f"No meter readings found for {billing_year}-{billing_month:02d}.")

    prev_reading = _get_previous_reading(db, billing_year, billing_month)
    if not prev_reading:
        raise ValueError(
            f"No prior month meter readings found for {billing_year}-{billing_month:02d}. "
            "Cannot compute consumption."
        )

    # Delete existing calculation (cascades to unit_allocations and step_allocations)
    existing = (
        db.query(BillingCalculation)
        .filter_by(billing_year=billing_year, billing_month=billing_month)
        .first()
    )
    if existing:
        db.delete(existing)
        db.flush()

    # Clear derived columns on the meter reading row
    _clear_derived_reading_columns(reading)
    db.flush()

    notes: list[str] = []

    # Step 1 — Raw consumption (full precision, no rounding)
    raw = _derive_raw_consumption(reading, prev_reading)

    # Step 2 — Common property (full precision)
    elec_common, water_common, clamped = _compute_common_property(raw)
    if clamped:
        notes.append(
            "Common property consumption clamped to zero (sum of unit readings "
            "exceeded total meter reading — check meter data)."
        )

    # Step 3 — CoJ adjustment factors (full precision)
    elec_factor, water_factor = _compute_adjustment_factors(
        raw, elec_common, water_common, elec_inv, water_inv
    )

    # Step 4 — Apply adjustment; write consumption + adjusted figures to MeterReading
    grossed_up = _apply_adjustment(raw, elec_common, water_common, elec_factor, water_factor)
    _write_consumption_to_reading(reading, raw, elec_common, water_common, grossed_up)
    db.flush()

    # Step 5 — Allocate step costs (full precision accumulation)
    elec_steps  = [li for li in elec_inv.line_items  if li.line_type == "step"]
    water_steps = [li for li in water_inv.line_items if li.line_type == "step"]

    elec_step_rows,  elec_var_costs  = _allocate_steps(elec_steps,  grossed_up, "electricity")
    water_step_rows, water_var_costs = _allocate_steps(water_steps, grossed_up, "water")

    # Step 6 — Fixed costs (full precision, sewer excluded from water)
    elec_fixed_items  = [li for li in elec_inv.line_items  if li.line_type == "fixed"]
    water_fixed_items = [li for li in water_inv.line_items if li.line_type == "fixed"]

    elec_fixed_total, _             = _compute_fixed_costs(elec_fixed_items,  "electricity", notes)
    water_fixed_total, sewer_incl_vat = _compute_fixed_costs(water_fixed_items, "water",        notes)

    # Reconciliation targets (VAT-inclusive):
    # electricity = total_due (VAT already included)
    # water       = total_due − sewer_incl_vat (sewer excluded from unit billing)
    elec_target  = _to_decimal(elec_inv.total_due)
    water_target = _to_decimal(water_inv.total_due) - sewer_incl_vat

    # VAT scaling factors: line items are stored ex-VAT; total_due is incl-VAT.
    # Factor ≈ 1.15. Kept at full Decimal precision throughout the calculation.
    elec_ex_vat_total  = sum(elec_var_costs.values())  + elec_fixed_total
    water_ex_vat_total = sum(water_var_costs.values()) + water_fixed_total

    if elec_ex_vat_total <= 0:
        raise ValueError("Electricity ex-VAT total is zero — cannot compute VAT factor.")
    if water_ex_vat_total <= 0:
        raise ValueError("Water ex-VAT total is zero — cannot compute VAT factor.")

    elec_vat_factor  = elec_target  / elec_ex_vat_total
    water_vat_factor = water_target / water_ex_vat_total

    notes.append(
        f"VAT scaling: electricity factor {elec_vat_factor:.6f} "
        f"(ex-VAT R{elec_ex_vat_total:.2f} → target R{elec_target}); "
        f"water factor {water_vat_factor:.6f} "
        f"(ex-VAT R{water_ex_vat_total:.2f} → target R{water_target})."
    )

    # Step 7 — Scale fixed costs by VAT factor
    elec_fixed_per_unit  = elec_fixed_total  * elec_vat_factor  / 5
    water_fixed_per_unit = water_fixed_total * water_vat_factor / 5

    # Step 7b — Common property variable cost (scaled, then split)
    elec_common_var_ex  = elec_var_costs["Common Property"]
    water_common_var_ex = water_var_costs["Common Property"]

    if elec_common_var_ex < 0 or water_common_var_ex < 0:
        raise ValueError("Common property variable cost is negative — algorithm error.")

    elec_common_var  = elec_common_var_ex  * elec_vat_factor
    water_common_var = water_common_var_ex * water_vat_factor

    elec_common_per_unit  = elec_common_var  / 5
    water_common_per_unit = water_common_var / 5

    # Step 8 — Per-unit totals (full precision — rounding adjustment applied next)
    unit_costs: dict[str, dict] = {}
    for label in UNIT_LABELS:
        ev = elec_var_costs[label]  * elec_vat_factor
        wv = water_var_costs[label] * water_vat_factor
        te = ev + elec_fixed_per_unit  + elec_common_per_unit
        tw = wv + water_fixed_per_unit + water_common_per_unit
        unit_costs[label] = {
            "elec_variable_cost":  ev,
            "water_variable_cost": wv,
            "elec_fixed_share":    elec_fixed_per_unit,
            "water_fixed_share":   water_fixed_per_unit,
            "elec_common_share":   elec_common_per_unit,
            "water_common_share":  water_common_per_unit,
            "total_elec":  te,
            "total_water": tw,
            "grand_total": te + tw,
        }

    # Step 9 — Rounding adjustment: brings sum of unit bills to equal targets exactly
    unit_costs = _apply_rounding_adjustment(unit_costs, elec_target, water_target, notes)

    # Step 10 — Reconciliation check (exact equality after adjustment)
    elec_units_total  = sum(unit_costs[l]["total_elec"]  for l in UNIT_LABELS)
    water_units_total = sum(unit_costs[l]["total_water"] for l in UNIT_LABELS)
    elec_reconciled  = abs(elec_units_total  - elec_target)  < Decimal("0.005")
    water_reconciled = abs(water_units_total - water_target) < Decimal("0.005")

    # --- Persist everything ---
    calc = BillingCalculation(
        billing_year  = billing_year,
        billing_month = billing_month,
        elec_adjustment_factor  = elec_factor,
        water_adjustment_factor = water_factor,
        elec_vat_factor  = elec_vat_factor,
        water_vat_factor = water_vat_factor,
        elec_total_fixed_cost  = elec_fixed_total,
        water_total_fixed_cost = water_fixed_total,
        elec_total_variable_cost  = sum(elec_var_costs.values())  * elec_vat_factor,
        water_total_variable_cost = sum(water_var_costs.values()) * water_vat_factor,
        elec_common_variable_cost  = elec_common_var,
        water_common_variable_cost = water_common_var,
        elec_reconciliation_target  = elec_target,
        water_reconciliation_target = water_target,
        elec_units_total  = elec_units_total,
        water_units_total = water_units_total,
        elec_reconciled  = elec_reconciled,
        water_reconciled = water_reconciled,
        common_property_clamped = clamped,
        notes = "\n".join(notes) if notes else None,
    )
    db.add(calc)
    db.flush()

    # Unit billing allocations
    for label in UNIT_LABELS:
        unit_num = int(label.split()[1])
        uc = unit_costs[label]
        db.add(UnitBillingAllocation(
            billing_calculation_id = calc.id,
            unit_number            = unit_num,
            elec_variable_cost     = uc["elec_variable_cost"],
            water_variable_cost    = uc["water_variable_cost"],
            elec_fixed_share       = uc["elec_fixed_share"],
            water_fixed_share      = uc["water_fixed_share"],
            elec_common_share      = uc["elec_common_share"],
            water_common_share     = uc["water_common_share"],
            total_elec             = uc["total_elec"],
            total_water            = uc["total_water"],
            grand_total            = uc["grand_total"],
        ))

    # Step allocation rows
    for row in elec_step_rows + water_step_rows:
        db.add(BillingStepAllocation(
            billing_calculation_id = calc.id,
            invoice_type    = row["invoice_type"],
            step_number     = row["step_number"],
            step_label      = row["step_label"],
            consumer_label  = row["consumer_label"],
            adjusted_usage = row["adjusted_usage"],
            usage_allocated  = row["usage_allocated"],
            rate             = row["rate"],
            cost             = row["cost"],
            sort_key         = row["sort_key"],
        ))

    db.commit()
    db.refresh(calc)
    return calc


# ---------------------------------------------------------------------------
# Private helpers — inputs
# ---------------------------------------------------------------------------

def _get_invoice(db: Session, year: int, month: int, invoice_type: str) -> Optional[CojInvoice]:
    return (
        db.query(CojInvoice)
        .filter_by(billing_year=year, billing_month=month, invoice_type=invoice_type)
        .first()
    )


def _get_reading(db: Session, year: int, month: int) -> Optional[MeterReading]:
    return db.query(MeterReading).filter_by(year=year, month=month).first()


def _get_previous_reading(db: Session, year: int, month: int) -> Optional[MeterReading]:
    """Return the most recent MeterReading strictly before the given year/month."""
    prev_year, prev_month = (year, month - 1) if month > 1 else (year - 1, 12)
    return db.query(MeterReading).filter_by(year=prev_year, month=prev_month).first()


def _to_decimal(value) -> Decimal:
    """Safely convert a DB Numeric/float/int/None to Decimal."""
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return Decimal("0")


# ---------------------------------------------------------------------------
# Private helpers — algorithm steps
# ---------------------------------------------------------------------------

def _derive_raw_consumption(current: MeterReading, previous: MeterReading) -> dict:
    """
    Step 1: Compute this month's consumption = current reading − previous reading.

    Returns a dict with keys elec_unit_1..5, elec_total, water_unit_1..5, water_total.
    All values are full-precision Decimal.
    Raises ValueError if any consumption figure is negative.
    """
    fields = [
        "elec_unit_1", "elec_unit_2", "elec_unit_3", "elec_unit_4", "elec_unit_5", "elec_total",
        "water_unit_1", "water_unit_2", "water_unit_3", "water_unit_4", "water_unit_5", "water_total",
    ]
    raw: dict[str, Decimal] = {}
    for key in fields:
        curr_val = _to_decimal(getattr(current,  key, None))
        prev_val = _to_decimal(getattr(previous, key, None))
        consumption = curr_val - prev_val
        if consumption < 0:
            raise ValueError(
                f"Negative consumption detected for '{key}' "
                f"(current={curr_val}, previous={prev_val}). "
                "Check meter readings for data entry errors or meter rollover."
            )
        raw[key] = consumption
    return raw


def _compute_common_property(raw: dict) -> tuple[Decimal, Decimal, bool]:
    """
    Step 2: Common property = max(0, total − sum of units).
    Returns (elec_common, water_common, clamped).
    clamped=True if either value was negative before clamping.
    """
    elec_sum  = sum(raw[f"elec_unit_{n}"]  for n in range(1, 6))
    water_sum = sum(raw[f"water_unit_{n}"] for n in range(1, 6))

    elec_raw_common  = raw["elec_total"]  - elec_sum
    water_raw_common = raw["water_total"] - water_sum

    clamped = elec_raw_common < 0 or water_raw_common < 0

    elec_common  = max(Decimal("0"), elec_raw_common)
    water_common = max(Decimal("0"), water_raw_common)

    return elec_common, water_common, clamped


def _compute_adjustment_factors(
    raw: dict,
    elec_common: Decimal,
    water_common: Decimal,
    elec_inv: CojInvoice,
    water_inv: CojInvoice,
) -> tuple[Decimal, Decimal]:
    """
    Step 3: CoJ adjustment factor = CoJ consumption ÷ our total consumption.
    Full Decimal precision — no rounding applied.
    Validates totals > 0 and factors within [0.5, 2.0].
    """
    our_elec  = sum(raw[f"elec_unit_{n}"]  for n in range(1, 6)) + elec_common
    our_water = sum(raw[f"water_unit_{n}"] for n in range(1, 6)) + water_common

    if our_elec <= 0:
        raise ValueError(
            "Total electricity consumption is zero — cannot compute adjustment factor. "
            "Check that meter readings were entered for both the current and previous month."
        )
    if our_water <= 0:
        raise ValueError(
            "Total water consumption is zero — cannot compute adjustment factor. "
            "Check that meter readings were entered for both the current and previous month."
        )

    coj_elec  = _to_decimal(elec_inv.consumption)
    coj_water = _to_decimal(water_inv.consumption)

    elec_factor  = coj_elec  / our_elec
    water_factor = coj_water / our_water

    if not (ADJ_FACTOR_MIN <= elec_factor <= ADJ_FACTOR_MAX):
        raise ValueError(
            f"Electricity adjustment factor {elec_factor:.4f} is outside expected bounds "
            f"({ADJ_FACTOR_MIN}–{ADJ_FACTOR_MAX}). "
            "Check meter readings and the CoJ electricity invoice for data errors."
        )
    if not (ADJ_FACTOR_MIN <= water_factor <= ADJ_FACTOR_MAX):
        raise ValueError(
            f"Water adjustment factor {water_factor:.4f} is outside expected bounds "
            f"({ADJ_FACTOR_MIN}–{ADJ_FACTOR_MAX}). "
            "Check meter readings and the CoJ water invoice for data errors."
        )

    return elec_factor, water_factor


def _apply_adjustment(
    raw: dict,
    elec_common: Decimal,
    water_common: Decimal,
    elec_factor: Decimal,
    water_factor: Decimal,
) -> dict:
    """
    Step 4: Multiply each consumer's raw consumption by the CoJ adjustment factor.
    Full Decimal precision — no rounding applied.
    Returns dict with keys like 'elec_unit_1_adjusted', 'elec_common_adjusted', etc.
    """
    grossed: dict[str, Decimal] = {}
    for n in range(1, 6):
        grossed[f"elec_unit_{n}_adjusted"]  = raw[f"elec_unit_{n}"]  * elec_factor
        grossed[f"water_unit_{n}_adjusted"] = raw[f"water_unit_{n}"] * water_factor
    grossed["elec_common_adjusted"]  = elec_common  * elec_factor
    grossed["water_common_adjusted"] = water_common * water_factor
    return grossed


def _write_consumption_to_reading(
    reading: MeterReading,
    raw: dict,
    elec_common: Decimal,
    water_common: Decimal,
    grossed_up: dict,
) -> None:
    """Write derived consumption and grossed-up figures back to the MeterReading row."""
    for n in range(1, 6):
        setattr(reading, f"elec_unit_{n}_consumption",  raw[f"elec_unit_{n}"])
        setattr(reading, f"water_unit_{n}_consumption", raw[f"water_unit_{n}"])
        setattr(reading, f"elec_unit_{n}_adjusted",   grossed_up[f"elec_unit_{n}_adjusted"])
        setattr(reading, f"water_unit_{n}_adjusted",  grossed_up[f"water_unit_{n}_adjusted"])
    reading.elec_common_consumption  = elec_common
    reading.water_common_consumption = water_common
    reading.elec_common_adjusted   = grossed_up["elec_common_adjusted"]
    reading.water_common_adjusted  = grossed_up["water_common_adjusted"]


def _clear_derived_reading_columns(reading: MeterReading) -> None:
    """Clear all derived columns on a MeterReading row (called before recalculation)."""
    for n in range(1, 6):
        setattr(reading, f"elec_unit_{n}_consumption", None)
        setattr(reading, f"water_unit_{n}_consumption", None)
        setattr(reading, f"elec_unit_{n}_adjusted", None)
        setattr(reading, f"water_unit_{n}_adjusted", None)
    reading.elec_common_consumption  = None
    reading.water_common_consumption = None
    reading.elec_common_adjusted   = None
    reading.water_common_adjusted  = None


def _allocate_steps(
    step_items: list[CojInvoiceLineItem],
    grossed_up: dict,
    invoice_type: str,
) -> tuple[list[dict], dict[str, Decimal]]:
    """
    Step 5: Allocate step kWh/kL equally among 6 consumers, handling exhaustion iteratively.

    All arithmetic is full Decimal precision. Values stored in DB row dicts are also
    full precision — rounding for display is done in templates.

    Returns (step_allocation_rows, variable_costs_per_consumer).
    variable_costs values are full-precision accumulated costs (ex-VAT).
    """
    prefix = "elec" if invoice_type == "electricity" else "water"

    consumer_totals: dict[str, Decimal] = {}
    for n in range(1, 6):
        consumer_totals[f"Unit {n}"] = _to_decimal(grossed_up[f"{prefix}_unit_{n}_adjusted"])
    consumer_totals["Common Property"] = _to_decimal(grossed_up[f"{prefix}_common_adjusted"])

    remaining_usage: dict[str, Decimal] = dict(consumer_totals)

    step_allocation_rows: list[dict] = []
    variable_costs: dict[str, Decimal] = defaultdict(Decimal)

    for step_num, step in enumerate(step_items, start=1):
        step_usage = _to_decimal(step.usage_amount)
        step_rate  = _to_decimal(step.rate)

        active = {c: remaining_usage[c] for c in CONSUMER_LABELS if remaining_usage[c] > 0}
        step_allocations: dict[str, Decimal] = {c: Decimal("0") for c in CONSUMER_LABELS}
        remaining_step = step_usage

        while remaining_step > Decimal("1E-9") and active:
            equal_share = remaining_step / len(active)
            exhausted: dict[str, Decimal] = {}

            for consumer, usage_left in active.items():
                if usage_left <= equal_share:
                    exhausted[consumer] = usage_left

            if not exhausted:
                for consumer in list(active.keys()):
                    step_allocations[consumer] += equal_share
                    remaining_usage[consumer]  -= equal_share
                remaining_step = Decimal("0")
            else:
                for consumer, used in exhausted.items():
                    step_allocations[consumer] += used
                    remaining_usage[consumer]   = Decimal("0")
                    remaining_step             -= used
                    del active[consumer]

        step_total_allocated = sum(step_allocations.values())
        if abs(step_total_allocated - step_usage) > Decimal("0.001"):
            raise ValueError(
                f"Step allocation error for {invoice_type} {step.label}: "
                f"allocated {step_total_allocated} but expected {step_usage}. "
                "This is an algorithm error — please report it."
            )

        for consumer in CONSUMER_LABELS:
            allocated  = step_allocations[consumer]
            cost       = allocated * step_rate
            variable_costs[consumer] += cost

            step_allocation_rows.append({
                "invoice_type":    invoice_type,
                "step_number":     step_num,
                "step_label":      step.label,
                "consumer_label":  consumer,
                "adjusted_usage": consumer_totals[consumer],
                "usage_allocated":  allocated,
                "rate":             step_rate,
                "cost":             cost,
                "sort_key":         f"{invoice_type}_{step_num:02d}_{consumer}",
            })

    return step_allocation_rows, dict(variable_costs)


def _compute_fixed_costs(
    fixed_items: list[CojInvoiceLineItem],
    invoice_type: str,
    notes: list[str],
) -> tuple[Decimal, Decimal]:
    """
    Step 6: Sum fixed line items.
    For water: exclude the 'Sewer charge' line item and its VAT (15%).

    Returns (billable_fixed_total, sewer_incl_vat). Full Decimal precision.
    sewer_incl_vat is 0 for electricity.
    """
    sewer_incl_vat = Decimal("0")
    total = Decimal("0")

    for item in fixed_items:
        cost = _to_decimal(item.cost)
        if invoice_type == "water" and item.label.lower().strip() == "sewer charge":
            sewer_incl_vat = cost * Decimal("1.15")
            continue
        total += cost

    if invoice_type == "water" and sewer_incl_vat == 0:
        notes.append(
            "No 'Sewer charge' line item found on the water invoice. "
            "Nothing excluded from water fixed costs — verify the invoice."
        )

    return total, sewer_incl_vat


def _apply_rounding_adjustment(
    unit_costs: dict,
    elec_target: Decimal,
    water_target: Decimal,
    notes: list[str],
) -> dict:
    """
    Step 9: Apply a small correction to Unit 1 so that the sum of all 5 unit bills
    equals the reconciliation target exactly.

    The diff is the exact arithmetic difference between the target and the sum of
    full-precision unit costs. It is added directly to Unit 1 without any rounding,
    so the reconciliation identity holds to full Decimal precision.

    Raises ValueError if the required adjustment exceeds R0.10 (which would indicate
    a genuine calculation error rather than a floating-point artefact).
    """
    elec_sum  = sum(unit_costs[l]["total_elec"]  for l in UNIT_LABELS)
    water_sum = sum(unit_costs[l]["total_water"] for l in UNIT_LABELS)

    elec_diff  = elec_target  - elec_sum
    water_diff = water_target - water_sum

    tolerance = Decimal("0.10")
    if abs(elec_diff) > tolerance:
        raise ValueError(
            f"Electricity rounding adjustment of R{elec_diff:.4f} exceeds tolerance of R{tolerance}. "
            "Check step allocation logic and invoice data."
        )
    if abs(water_diff) > tolerance:
        raise ValueError(
            f"Water rounding adjustment of R{water_diff:.4f} exceeds tolerance of R{tolerance}. "
            "Check step allocation logic and invoice data."
        )

    if elec_diff != 0:
        unit_costs["Unit 1"]["elec_variable_cost"] += elec_diff
        unit_costs["Unit 1"]["total_elec"]          += elec_diff
        unit_costs["Unit 1"]["grand_total"]          += elec_diff
        notes.append(f"Electricity rounding adjustment of R{elec_diff:.4f} applied to Unit 1.")

    if water_diff != 0:
        unit_costs["Unit 1"]["water_variable_cost"] += water_diff
        unit_costs["Unit 1"]["total_water"]          += water_diff
        unit_costs["Unit 1"]["grand_total"]          += water_diff
        notes.append(f"Water rounding adjustment of R{water_diff:.4f} applied to Unit 1.")

    return unit_costs


# ---------------------------------------------------------------------------
# Public helper — used by the router to build list-page data
# ---------------------------------------------------------------------------

def get_billing_periods(db: Session) -> list[dict]:
    """
    Return all billing months that have any CoJ invoice or meter reading data,
    joined to their BillingCalculation if one exists. Sorted newest first.
    """
    from sqlalchemy import text

    rows = db.execute(text("""
        SELECT DISTINCT billing_year, billing_month
        FROM (
            SELECT billing_year, billing_month FROM coj_invoices
                WHERE billing_year IS NOT NULL AND billing_month IS NOT NULL
            UNION
            SELECT year AS billing_year, month AS billing_month FROM meter_readings
        )
        ORDER BY billing_year DESC, billing_month DESC
    """)).fetchall()

    result = []
    for row in rows:
        yr, mo = row[0], row[1]
        calc = (
            db.query(BillingCalculation)
            .filter_by(billing_year=yr, billing_month=mo)
            .first()
        )
        result.append({"billing_year": yr, "billing_month": mo, "calculation": calc})

    return result
