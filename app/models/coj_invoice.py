"""
Database models for Module 2b: CoJ Bill Parsing.

Two tables:
  - CojInvoice: one row per invoice (electricity or water), keyed by type + year + month.
  - CojInvoiceLineItem: child rows for variable line items (steps and fixed charges).
"""

from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class CojInvoice(Base):
    __tablename__ = "coj_invoices"

    id = Column(Integer, primary_key=True, index=True)

    # 'electricity' or 'water'
    invoice_type = Column(String, nullable=False)

    # The statement period printed on the invoice (e.g. April 2026 → year=2026, month=4)
    statement_year = Column(Integer, nullable=False)
    statement_month = Column(Integer, nullable=False)

    # The actual billing period: one month behind statement (March invoice = Feb billing)
    billing_year = Column(Integer, nullable=True)
    billing_month = Column(Integer, nullable=True)

    # Header fields from the invoice
    invoice_date = Column(Date, nullable=True)
    invoice_number = Column(String, nullable=True)
    account_number = Column(String, nullable=True)
    payment_due_date = Column(Date, nullable=True)

    # CoJ meter reading period (differs from Barry's reading dates)
    reading_period_start = Column(Date, nullable=True)
    reading_period_end = Column(Date, nullable=True)

    # Meter reading data
    start_reading = Column(Numeric(12, 4), nullable=True)
    end_reading = Column(Numeric(12, 4), nullable=True)
    consumption = Column(Numeric(12, 4), nullable=True)  # as explicitly printed on invoice

    # Totals
    total_vat = Column(Numeric(10, 2), nullable=True)
    total_due = Column(Numeric(10, 2), nullable=True)

    # Path to the saved PDF on disk, relative to the project root
    pdf_path = Column(String, nullable=True)

    status = Column(String, nullable=False, default="saved")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # One invoice has many line items
    line_items = relationship(
        "CojInvoiceLineItem",
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="CojInvoiceLineItem.sort_order"
    )

    # Only one electricity and one water invoice per statement month
    __table_args__ = (
        UniqueConstraint("invoice_type", "statement_year", "statement_month",
                         name="uq_coj_invoices_type_year_month"),
    )


class CojInvoiceLineItem(Base):
    __tablename__ = "coj_invoice_line_items"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("coj_invoices.id"), nullable=False)

    # 'step' for usage steps, 'fixed' for fixed charges (service fee, sewer, etc.)
    line_type = Column(String, nullable=False)

    # Human-readable label as it appears on the invoice
    label = Column(String, nullable=False)

    # Steps only: the usage quantity (kWh or KL) and tariff rate (R per unit)
    # Cost per step is computed as usage_amount × rate — not stored separately
    usage_amount = Column(Numeric(12, 4), nullable=True)
    rate = Column(Numeric(10, 6), nullable=True)

    # Fixed charges: rand amount as printed. Steps: computed cost (usage × rate).
    cost = Column(Numeric(10, 2), nullable=False)

    # Preserves the display order from the invoice
    sort_order = Column(Integer, nullable=False, default=0)

    invoice = relationship("CojInvoice", back_populates="line_items")
