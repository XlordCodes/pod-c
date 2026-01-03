from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime, timezone
from app.database import Base

class Invoice(Base):
    """
    Represents a financial invoice issued to a Contact.
    """
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    
    # Link to CRM Contact
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=False, index=True)
    
    # Financials (Using Numeric for money is safer than Float/Int)
    total_amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="USD")
    
    # Status Workflow
    status = Column(String, default="draft", index=True) # draft, sent, paid, overdue, cancelled
    
    due_date = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    contact = relationship("app.models.crm.Contact", back_populates="invoices")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="invoice")

class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    
    description = Column(String, nullable=False)
    quantity = Column(Integer, default=1)
    unit_price = Column(Numeric(10, 2), nullable=False)
    
    invoice = relationship("Invoice", back_populates="items")

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    
    amount = Column(Numeric(10, 2), nullable=False)
    method = Column(String, default="bank_transfer") # stripe, cash, bank_transfer
    reference_id = Column(String, nullable=True) # External Transaction ID
    
    payment_date = Column(DateTime(timezone=True), server_default=func.now())
    
    invoice = relationship("Invoice", back_populates="payments")

class LedgerEntry(Base):
    """
    Double-entry bookkeeping log. Immutable audit trail of money movement.
    """
    __tablename__ = "ledger_entries"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    
    transaction_type = Column(String, nullable=False) # credit, debit
    amount = Column(Numeric(10, 2), nullable=False)
    description = Column(String, nullable=False)
    
    # Link to source entity (Polymorphic-style association can be done via ID + Type)
    reference_entity = Column(String, nullable=True) # e.g. "Invoice"
    reference_id = Column(Integer, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())