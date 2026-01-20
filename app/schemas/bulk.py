# app/schemas/bulk.py
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime

# ----------------------------
# BulkMessage Schemas
# ----------------------------

class BulkMessageBase(BaseModel):
    to_number: str
    status: str

class BulkMessage(BulkMessageBase):
    id: int
    attempts: int
    last_error: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# ----------------------------
# BulkJob Schemas
# ----------------------------

class BulkJobCreate(BaseModel):
    """Schema for creating a new job."""
    template_name: str = Field(..., description="WhatsApp template name.")
    language_code: str = Field("en_US", description="Language code.")
    numbers: List[str] = Field(..., min_length=1, description="List of phone numbers.")
    
    scheduled_at: Optional[datetime] = Field(None, description="Schedule time.")
    components: Optional[List[dict]] = Field(None, description="Template variables.")


class BulkJobResponse(BaseModel):
    """Schema for the response after creating a job."""
    id: int
    tenant_id: int          # <--- ADDED (Matches DB)
    template_name: str
    language_code: str
    components: Optional[List[dict]] = None
    status: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class BulkJobStatus(BaseModel):
    """Schema for checking status."""
    id: int
    status: str
    created_at: datetime
    messages: List[BulkMessage]

    model_config = ConfigDict(from_attributes=True)