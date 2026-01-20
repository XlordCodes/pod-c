# app/schemas/crm.py
"""
Module: CRM Schemas
Context: Pod B - Data Validation Layer

Defines Pydantic models for Lead and Deal operations.
Ensures strict typing for API requests and responses.
"""

from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
from datetime import datetime

# --- Lead Schemas ---

class LeadCreate(BaseModel):
    """Payload for creating a new Lead."""
    name: str = Field(..., min_length=2, description="Full name of the lead")
    email: Optional[EmailStr] = Field(None, description="Contact email")

class LeadOut(BaseModel):
    """Response model for Lead details."""
    id: int
    name: str
    email: Optional[EmailStr] = None
    status: str
    created_at: datetime
    tenant_id: int
    owner_id: int

    model_config = ConfigDict(from_attributes=True)

# --- Deal Schemas ---

class PromoteRequest(BaseModel):
    """
    Payload for promoting a Lead to a Deal.
    Requires value in cents (e.g., $100.00 = 10000).
    """
    value_cents: int = Field(..., gt=0, description="Deal value in cents")
    seller_id: Optional[int] = Field(None, description="ID of the user assigned to this deal")

class DealOut(BaseModel):
    """Response model for Deal details."""
    id: int
    lead_id: int
    value_cents: int
    seller_id: Optional[int] = None
    created_at: datetime
    tenant_id: int

    model_config = ConfigDict(from_attributes=True)