from pydantic import BaseModel, Field
from typing import List, Optional
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

    class Config:
        from_attributes = True # Replaces orm_mode

# ----------------------------
# BulkJob Schemas
# ----------------------------

class BulkJobCreate(BaseModel):
    """Schema for creating a new job, matching the WhatsApp payload requirements."""
    template_name: str = Field(..., description="The approved WhatsApp template name.")
    language_code: str = Field("en_US", description="The language code (e.g., 'en_US', 'es').")
    numbers: List[str] = Field(..., min_length=1, description="A list of 'to' numbers in E.164 format.")
    # Parameters for variables (headers, body, buttons). Must be a valid Meta components structure.
    components: Optional[List[dict]] = Field(None, description="Optional template parameters/components (e.g., {{1}} variable data).")


class BulkJobResponse(BaseModel):
    """Schema for the response after creating a job."""
    id: int
    template_name: str
    language_code: str
    components: Optional[List[dict]] = None
    status: str
    created_at: datetime
    numbers: List[str]

class BulkJobStatus(BaseModel):
    """Schema for checking a job's status."""
    id: int
    status: str
    created_at: datetime
    messages: List[BulkMessage]

    class Config:
        from_attributes = True # Replaces orm_mode