"""
Database models for Module 11: Insurance Documents.

Two tables:
  - InsurancePolicy: one row per policy period (e.g. 2026–2027 renewal).
  - InsuranceDocument: one row per PDF, linked to a policy. Stores the
    extracted text (with page markers) and key facts JSON extracted by Groq.
"""

from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class InsurancePolicy(Base):
    __tablename__ = "insurance_policies"

    id = Column(Integer, primary_key=True, index=True)

    # Human-readable label, e.g. "2026–2027 Renewal"
    label = Column(String, nullable=False)
    insurer_name = Column(String, nullable=True)
    policy_number = Column(String, nullable=True)
    cover_start_date = Column(Date, nullable=True)
    cover_end_date = Column(Date, nullable=True)
    total_premium = Column(Numeric(12, 2), nullable=True)  # ZAR
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    # cascade="all, delete-orphan" means deleting a policy also deletes its documents
    documents = relationship(
        "InsuranceDocument",
        back_populates="policy",
        cascade="all, delete-orphan",
        order_by="InsuranceDocument.uploaded_at",
    )


class InsuranceDocument(Base):
    __tablename__ = "insurance_documents"

    id = Column(Integer, primary_key=True, index=True)
    policy_id = Column(Integer, ForeignKey("insurance_policies.id"), nullable=False)

    document_name = Column(String, nullable=False)  # User-given name, e.g. "Policy Schedule"

    # One of: policy, renewal_schedule, sasria, broker, other
    document_type = Column(String, nullable=False)

    # Relative path from project root: documents/insurance/...
    file_path = Column(String, nullable=True)

    page_count = Column(Integer, nullable=True)

    # Full extracted text with [Page N] markers, for use in Q&A context
    extracted_text = Column(Text, nullable=True)

    # JSON string of key facts extracted by Groq on upload, e.g.
    # {"insurer": "...", "main_covers": [...], "claims_excess": "..."}
    key_facts_json = Column(Text, nullable=True)

    uploaded_at = Column(DateTime, server_default=func.now())

    policy = relationship("InsurancePolicy", back_populates="documents")
