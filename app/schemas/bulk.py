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
    """Schema for creating a new job."""
    template: str = Field(..., description="The name of the WhatsApp template to send.")
    numbers: List[str] = Field(..., min_length=1, description="A list of 'to' numbers in E.164 format.")

class BulkJobResponse(BaseModel):
    """Schema for the response after creating a job."""
    job_id: int
    template: str
    status: str
    created_at: datetime
    numbers: List[str]

class BulkJobStatus(BaseModel):
    """Schema for checking a job's status."""
    job_id: int
    status: str
    created_at: datetime
    messages: List[BulkMessage]

    class Config:
        from_attributes = True # Replaces orm_mode