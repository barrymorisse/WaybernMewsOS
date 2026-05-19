"""
Database models for Module 2c: Utility Consumption & Allocation.

Three tables:
  - BillingCalculation: one row per billing month — gross-up factors, fixed/variable
    cost totals, and reconciliation results.
  - UnitBillingAllocation: five rows per calculation (one per unit) — cost breakdown
    for electricity and water. Consumption figures live on MeterReading, not here.
  - BillingStepAllocation: one row per consumer per step — the full step-by-step
    workings used to render the detail page.
"""

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String,
    Text, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class BillingCalculation(Base):
    __tablename__ = "billing_calculations"

    id = Column(Integer, primary_key=True, index=True)
    billing_year  = Column(Integer, nullable=False)
    billing_month = Column(Integer, nullable=False)
    calculated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # CoJ adjustment factors (CoJ consumption ÷ our total consumption), stored to 6dp
    elec_adjustment_factor  = Column(Numeric(10, 6), nullable=True)
    water_adjustment_factor = Column(Numeric(10, 6), nullable=True)

    # VAT scaling factors (reconciliation_target ÷ ex-VAT cost total).
    # Line items in coj_invoice_line_items are stored ex-VAT; total_due is VAT-inclusive.
    # These factors (≈1.15) are applied to each unit's ex-VAT allocation to produce
    # the final incl-VAT unit bills that sum exactly to the reconciliation target.
    elec_vat_factor  = Column(Numeric(10, 6), nullable=True)
    water_vat_factor = Column(Numeric(10, 6), nullable=True)

    # Fixed cost totals (electricity: all fixed items; water: all except sewer + sewer VAT)
    elec_total_fixed_cost  = Column(Numeric(10, 2), nullable=True)
    water_total_fixed_cost = Column(Numeric(10, 2), nullable=True)

    # Variable (step) cost totals summed across all 6 consumers
    elec_total_variable_cost  = Column(Numeric(10, 2), nullable=True)
    water_total_variable_cost = Column(Numeric(10, 2), nullable=True)

    # Common property's share of variable costs (before splitting across units)
    elec_common_variable_cost  = Column(Numeric(10, 2), nullable=True)
    water_common_variable_cost = Column(Numeric(10, 2), nullable=True)

    # Reconciliation targets: what the 5-unit totals must sum to
    elec_reconciliation_target  = Column(Numeric(10, 2), nullable=True)
    water_reconciliation_target = Column(Numeric(10, 2), nullable=True)  # CoJ total − sewer incl VAT

    # Actual sums of the 5 unit bills (should equal targets after rounding adjustment)
    elec_units_total  = Column(Numeric(10, 2), nullable=True)
    water_units_total = Column(Numeric(10, 2), nullable=True)

    # Reconciliation flags
    elec_reconciled  = Column(Boolean, nullable=True)
    water_reconciled = Column(Boolean, nullable=True)

    # True if common property consumption was clamped to zero (metering discrepancy)
    common_property_clamped = Column(Boolean, default=False)

    # Free-text field for warnings, clamping notes, rounding adjustments
    notes = Column(Text, nullable=True)

    # Module 2d — generated PDF report
    pdf_path         = Column(String,   nullable=True)
    pdf_generated_at = Column(DateTime, nullable=True)

    # One calculation → many unit allocations and step allocations
    unit_allocations = relationship(
        "UnitBillingAllocation",
        back_populates="calculation",
        cascade="all, delete-orphan",
        order_by="UnitBillingAllocation.unit_number",
    )
    step_allocations = relationship(
        "BillingStepAllocation",
        back_populates="calculation",
        cascade="all, delete-orphan",
        order_by="BillingStepAllocation.sort_key",
    )

    __table_args__ = (
        UniqueConstraint("billing_year", "billing_month", name="uq_billing_calculations_year_month"),
    )


class UnitBillingAllocation(Base):
    """Cost breakdown for one unit in one billing month. Five rows per BillingCalculation."""

    __tablename__ = "unit_billing_allocations"

    id                    = Column(Integer, primary_key=True, index=True)
    billing_calculation_id = Column(Integer, ForeignKey("billing_calculations.id"), nullable=False)
    unit_number           = Column(Integer, nullable=False)  # 1–5

    # Variable cost: this unit's share of electricity/water step costs
    elec_variable_cost  = Column(Numeric(10, 2), nullable=True)
    water_variable_cost = Column(Numeric(10, 2), nullable=True)

    # Fixed cost share: total fixed costs ÷ 5
    elec_fixed_share  = Column(Numeric(10, 2), nullable=True)
    water_fixed_share = Column(Numeric(10, 2), nullable=True)

    # Common property share: common property variable cost ÷ 5
    elec_common_share  = Column(Numeric(10, 2), nullable=True)
    water_common_share = Column(Numeric(10, 2), nullable=True)

    # Subtotals
    total_elec  = Column(Numeric(10, 2), nullable=True)  # variable + fixed + common
    total_water = Column(Numeric(10, 2), nullable=True)
    grand_total = Column(Numeric(10, 2), nullable=True)

    calculation = relationship("BillingCalculation", back_populates="unit_allocations")


class BillingStepAllocation(Base):
    """
    One row per consumer per step per invoice type.
    Used to render the step-by-step workings table on the detail page.
    """

    __tablename__ = "billing_step_allocations"

    id                     = Column(Integer, primary_key=True, index=True)
    billing_calculation_id  = Column(Integer, ForeignKey("billing_calculations.id"), nullable=False)

    invoice_type   = Column(String, nullable=False)   # 'electricity' or 'water'
    step_number    = Column(Integer, nullable=False)   # 1-based, for ordering
    step_label     = Column(String, nullable=False)    # e.g. 'Step 1' from the invoice
    consumer_label = Column(String, nullable=False)    # 'Unit 1'…'Unit 5' or 'Common Property'

    # Consumer's total adjusted usage (for reference — same for all steps of same consumer)
    adjusted_usage = Column(Numeric(12, 4), nullable=True)

    # How much of this step the consumer was allocated
    usage_allocated = Column(Numeric(12, 4), nullable=True)

    rate = Column(Numeric(10, 6), nullable=True)       # tariff rate for this step
    cost = Column(Numeric(10, 2), nullable=True)        # usage_allocated × rate, rounded to 2dp

    # Composite sort key so results come back in the right order without a multi-column ORDER BY
    # Format: "electricity_01_Unit 1", "electricity_01_Common Property", etc.
    sort_key = Column(String, nullable=False, default="")

    calculation = relationship("BillingCalculation", back_populates="step_allocations")
