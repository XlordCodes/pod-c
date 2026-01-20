# app/schemas/audit.py
"""
Module: Audit Schemas
Context: Pod B - Module 3 (Data Transfer Objects)

Defines the output structure for Audit Logs and Activity Feeds.
Uses Pydantic for validation and serialization.
"""

from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

# --- Shared User Schema (Minimal) ---
class AuditActor(BaseModel):
    id: int
    email: str
    
    model_config = ConfigDict(from_attributes=True)

# --- Audit Log Schemas ---

class AuditLogOut(BaseModel):
    """
    Response model for a system audit log.
    Immutable history of an action.
    """
    id: int
    action: str = Field(..., description="The action performed (create, update, delete)")
    entity: str = Field(..., description="The resource type (e.g., Invoice, Lead)")
    entity_id: Optional[int] = Field(None, description="ID of the affected resource")
    
    # Detailed changes stored as JSON
    changes: Optional[Dict[str, Any]] = Field(default={}, description="Snapshot of changes")
    
    # Metadata (IP, etc)
    meta: Optional[Dict[str, Any]] = Field(default={}, description="Request metadata")
    
    # Actor info (Optional because system events might have no user)
    actor_id: Optional[int]
    actor: Optional[AuditActor] = None # Nested user details
    
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# --- Activity Feed Schemas ---

class ActivityFeedOut(BaseModel):
    """
    Response model for the user's activity timeline.
    Human-readable messages.
    """
    id: int
    message: str = Field(..., description="Human readable activity description")
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)