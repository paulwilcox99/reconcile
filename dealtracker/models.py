from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, unique=True)
    email = Column(String)
    phone = Column(String)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    deals = relationship("Deal", back_populates="customer")
    documents = relationship("Document", back_populates="customer")

    def __repr__(self):
        return f"<Customer id={self.id} name={self.name!r}>"


class Deal(Base):
    __tablename__ = "deals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reference_number = Column(String, nullable=False, unique=True)  # e.g. JOB-2025-001
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    description = Column(Text, nullable=False)
    description_slug = Column(String, nullable=False)
    status = Column(String, nullable=False, default="open")
    # open | reconciled | disputed | closed | incomplete
    agreed_amount = Column(Float)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    customer = relationship("Customer", back_populates="deals")
    documents = relationship("Document", back_populates="deal", order_by="Document.confirmed_date")
    reconciliation_snapshots = relationship("ReconciliationSnapshot", back_populates="deal")

    def __repr__(self):
        return f"<Deal id={self.id} description={self.description!r} status={self.status}>"


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    deal_id = Column(Integer, ForeignKey("deals.id"), nullable=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)

    file_path = Column(String, nullable=False, unique=True)
    original_filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # pdf | image | text | email

    doc_type = Column(String)
    # estimate_request | estimate | quote_request | quote |
    # purchase_order | invoice | payment | receipt | unknown

    # AI-extracted (raw, pre-confirmation)
    ai_extracted_date = Column(String)
    ai_customer_name = Column(String)
    ai_deal_description = Column(Text)
    ai_doc_type = Column(String)
    ai_total_amount = Column(Float)
    ai_currency = Column(String, default="USD")
    ai_notes = Column(Text)
    ai_confidence = Column(Float)
    ai_raw_response = Column(Text)

    # Confirmed (after user review)
    confirmed_date = Column(String)
    confirmed_customer_name = Column(String)
    confirmed_deal_description = Column(Text)
    confirmed_doc_type = Column(String)
    confirmed_total_amount = Column(Float)
    confirmed_notes = Column(Text)
    is_confirmed = Column(Boolean, default=False, nullable=False)

    ai_provider = Column(String)   # openai | anthropic
    ai_model = Column(String)
    ingested_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    confirmed_at = Column(DateTime)

    deal = relationship("Deal", back_populates="documents")
    customer = relationship("Customer", back_populates="documents")

    def __repr__(self):
        return f"<Document id={self.id} type={self.doc_type!r} confirmed={self.is_confirmed}>"


class ReconciliationSnapshot(Base):
    __tablename__ = "reconciliation_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    deal_id = Column(Integer, ForeignKey("deals.id"), nullable=False)
    run_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    agreed_amount = Column(Float)
    invoiced_amount = Column(Float)
    paid_amount = Column(Float)

    quote_doc_ids = Column(Text)    # JSON array
    invoice_doc_ids = Column(Text)  # JSON array
    payment_doc_ids = Column(Text)  # JSON array

    invoice_vs_quote_delta = Column(Float)
    payment_vs_invoice_delta = Column(Float)
    has_discrepancy = Column(Boolean, default=False, nullable=False)
    discrepancy_notes = Column(Text)

    status = Column(String, nullable=False)
    # clean | over_billed | under_billed | under_paid | over_paid | missing_docs | incomplete

    deal = relationship("Deal", back_populates="reconciliation_snapshots")

    def __repr__(self):
        return f"<ReconciliationSnapshot id={self.id} deal_id={self.deal_id} status={self.status}>"
