# app/schemas/inventory.py
"""
Module: Inventory Schemas
Context: Pod B - Module 5 (Inventory Domain).

Defines Pydantic models for Product management and Stock adjustments.
Strictly matches the SQLAlchemy models for auto-mapping.
"""

from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict, field_validator

# --- SHARED BASES ---

class ProductBase(BaseModel):
    """
    Shared properties for Product input/output.
    """
    sku: str = Field(..., min_length=3, max_length=50, description="Unique Stock Keeping Unit (e.g., 'WIDGET-001')")
    name: str = Field(..., min_length=2, max_length=100, description="Product Name")
    description: Optional[str] = Field(None, max_length=500)
    price: Decimal = Field(..., gt=0, decimal_places=2, description="Unit Price")
    reorder_point: int = Field(default=10, ge=0, description="Low stock alert threshold")

# --- INPUT MODELS ---

class ProductCreate(ProductBase):
    """
    Schema for creating a new product catalog entry.
    Note: Initial stock is always 0. Use the adjustment endpoint to add initial inventory.
    """
    pass

class StockAdjustment(BaseModel):
    """
    Schema for manually adjusting stock (Restocking, Damage, etc).
    """
    qty: int = Field(..., description="Integer amount to add (positive) or remove (negative).")
    reason: str = Field(..., min_length=3, description="Reason for adjustment (e.g., 'restock', 'correction').")
    reference_id: Optional[str] = Field(None, description="External reference (e.g., 'PO-500', 'INV-102').")

    @field_validator('qty')
    def qty_cannot_be_zero(cls, v):
        if v == 0:
            raise ValueError('Adjustment quantity cannot be zero')
        return v

# --- OUTPUT MODELS ---

class StockTransactionResponse(BaseModel):
    """
    Immutable audit record of a stock movement.
    """
    id: int
    product_id: int
    
    # Renamed from 'change_amount' to match DB Model 'qty_change'
    qty_change: int 
    
    reason: str
    reference_id: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ProductResponse(ProductBase):
    """
    Full product details including current stock level.
    """
    id: int
    tenant_id: int
    
    # Renamed from 'stock_level' to match DB Model 'stock'
    stock: int
    
    created_at: datetime
    
    # Optional: We usually don't embed full transactions in list views for performance
    # transactions: List[StockTransactionResponse] = []

    model_config = ConfigDict(from_attributes=True)