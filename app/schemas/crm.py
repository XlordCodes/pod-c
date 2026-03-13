"""
Module: CRM Schemas
Context: Pod B - Data Validation Layer

Defines Pydantic models for Contact, Lead, and Deal operations.
Ensures strict typing and validation for API requests and responses.
"""

from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum
import re

# --- Contact Schemas ---

class ContactBase(BaseModel):
    """
    Shared properties for Contact creation and updates.
    """
    name: str = Field(..., min_length=1, description="Full name of the contact")
    email: Optional[EmailStr] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="E.164 formatted phone number")
    custom_fields: Optional[Dict[str, Any]] = Field(
        default_factory=dict, 
        description="Arbitrary JSON data for custom attributes (e.g., source, preferences)"
    )

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """
        Normalizes phone numbers to E.164 format.
        Removes spaces, dashes, and parentheses.
        """
        if v is None:
            return v
        
        # Remove common formatting characters
        clean_number = re.sub(r'[\s\-\(\)]', '', v)
        
        # Regex check for standard E.164 (e.g., +14155552671)
        # Allows 10-15 digits.
        if not re.match(r'^\+?[1-9]\d{9,14}$', clean_number):
            raise ValueError('Phone number must be in valid E.164 format (e.g., +14155552671)')
            
        return clean_number

class ContactCreate(ContactBase):
    """
    Payload for creating a new Contact.
    Inherits validation from ContactBase.
    """
    pass

class ContactUpdate(BaseModel):
    """
    Payload for patching a Contact (Partial Update).
    All fields are optional.
    """
    name: Optional[str] = Field(None, min_length=1)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    custom_fields: Optional[Dict[str, Any]] = None
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        # Reuse logic from Base (duplicated here because Pydantic partial models don't inherit validators easily without mixins)
        if v is None:
            return v
        clean_number = re.sub(r'[\s\-\(\)]', '', v)
        if not re.match(r'^\+?[1-9]\d{9,14}$', clean_number):
            raise ValueError('Phone number must be in valid E.164 format')
        return clean_number

class ContactOut(ContactBase):
    """
    Response model for Contact details.
    Includes system-generated fields.
    """
    id: int
    tenant_id: Optional[int] = None # Optional because legacy contacts might lack it
    owner_id: int
    created_at: datetime

    # Pydantic V2 config for ORM compatibility
    model_config = ConfigDict(from_attributes=True)


# --- Lead Schemas ---

class LeadStatus(str, Enum):
    """Strict typing for lead pipeline stages."""
    new = "new"
    contacted = "contacted"
    qualified = "qualified"
    converted = "converted"

class LeadCreate(BaseModel):
    """Payload for creating a new Lead."""
    name: str = Field(..., min_length=2, description="Full name of the lead")
    email: Optional[EmailStr] = Field(None, description="Contact email")

class LeadUpdate(BaseModel):
    """
    Payload for updating a Lead (Partial Update).
    All fields are optional.
    
    SECURITY: Converted leads cannot be updated (enforced in service layer).
    """
    name: Optional[str] = Field(None, min_length=2, description="Full name of the lead")
    email: Optional[EmailStr] = Field(None, description="Contact email")
    status: Optional[LeadStatus] = Field(None, description="Update the current pipeline stage")

class LeadOut(BaseModel):
    """Response model for Lead details."""
    id: int
    name: str
    email: Optional[EmailStr] = None
    status: LeadStatus
    created_at: datetime
    tenant_id: int
    owner_id: int

    model_config = ConfigDict(from_attributes=True)


# --- Deal Schemas ---

class PromoteRequest(BaseModel):
    """
    Payload for promoting a Lead to a Deal.
    Requires value in cents to prevent floating-point errors (e.g., $100.00 = 10000).
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