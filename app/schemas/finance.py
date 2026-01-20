# app/schemas/finance.py
"""
Module: Finance Pydantic Schemas
Context: Pod B - Finance Domain.

Defines the data validation rules for Invoices, Payments, and Ledger entries.
Prioritizes decimal accuracy for monetary values.
"""

from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict, field_validator

# --- SHARED BASES ---

class InvoiceItemBase(BaseModel):
    description: str = Field(..., min_length=3, description="Line item description")
    quantity: int = Field(default=1, gt=0, description="Quantity, must be positive")
    unit_price: Decimal = Field(..., gt=0, decimal_places=2, description="Price per unit")

class PaymentBase(BaseModel):
    amount: Decimal = Field(..., gt=0, decimal_places=2, description="Payment amount")
    method: str = Field(default="bank_transfer", description="e.g. stripe, cash, bank_transfer")
    reference_id: Optional[str] = Field(None, description="External transaction ID")

# --- INPUT MODELS (Create/Update) ---

class InvoiceItemCreate(InvoiceItemBase):
    """Schema for creating an item inside an invoice."""
    pass

class InvoiceCreate(BaseModel):
    """
    Schema for creating a new Invoice.
    Includes nested items to allow atomic creation.
    """
    contact_id: int = Field(..., description="ID of the CRM Contact")
    currency: str = Field(default="USD", min_length=3, max_length=3)
    due_date: Optional[datetime] = None
    items: List[InvoiceItemCreate] = Field(..., min_length=1, description="At least one line item is required")

    @field_validator('currency')
    def uppercase_currency(cls, v):
        return v.upper()

class PaymentCreate(PaymentBase):
    """Schema for recording a payment against an invoice."""
    invoice_id: int

# --- OUTPUT MODELS (Responses) ---

class InvoiceItemResponse(InvoiceItemBase):
    id: int
    invoice_id: int
    
    # Allow SQLAlchemy models to be converted to Pydantic
    model_config = ConfigDict(from_attributes=True)

class PaymentResponse(PaymentBase):
    id: int
    invoice_id: int
    payment_date: datetime
    tenant_id: int

    model_config = ConfigDict(from_attributes=True)

class InvoiceResponse(BaseModel):
    """
    Full Invoice representation including calculated totals and nested items.
    """
    id: int
    tenant_id: int
    contact_id: int
    
    total_amount: Decimal
    currency: str
    status: str
    due_date: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
    
    # Nested relations
    items: List[InvoiceItemResponse] = []
    payments: List[PaymentResponse] = []

    model_config = ConfigDict(from_attributes=True)

class LedgerEntryResponse(BaseModel):
    id: int
    transaction_type: str
    amount: Decimal
    description: str
    reference_entity: Optional[str]
    reference_id: Optional[int]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)