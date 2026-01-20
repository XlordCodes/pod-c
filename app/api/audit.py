# app/api/audit.py
"""
Module: Audit API
Context: Pod B - Module 3 (Interface Layer)

Exposes read-only endpoints for:
1. System Audit Logs (Compliance/Debugging)
2. User Activity Feeds (Dashboard Timeline)
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.authentication.router import get_current_user
from app.models.auth import User

# Import Service & Schemas
from app.services.audit_service import AuditService
from app.schemas.audit import AuditLogOut, ActivityFeedOut

router = APIRouter()

# --- Dependency ---
def get_audit_service(db: Session = Depends(get_db)) -> AuditService:
    return AuditService(db)

# --- Endpoints ---

@router.get("/logs", response_model=List[AuditLogOut])
def list_audit_logs(
    entity: Optional[str] = Query(None, description="Filter by entity type (e.g., 'Lead')"),
    user_id: Optional[int] = Query(None, description="Filter by Actor ID"),
    limit: int = Query(50, ge=1, le=1000),
    skip: int = Query(0, ge=0),
    service: AuditService = Depends(get_audit_service),
    current_user: User = Depends(get_current_user)
):
    """
    Get system-wide audit logs for the tenant.
    Useful for admins to see 'Who changed what'.
    """
    if not current_user.tenant_id:
        return []

    # Note: We access the repo through the service to keep layers clean.
    # The Repo's list_logs method filters by tenant_id automatically.
    return service.audit_repo.list_logs(
        tenant_id=current_user.tenant_id,
        entity=entity,
        limit=limit, 
        skip=skip
    )

@router.get("/activity", response_model=List[ActivityFeedOut])
def get_my_activity(
    limit: int = Query(20, ge=1, le=100),
    service: AuditService = Depends(get_audit_service),
    current_user: User = Depends(get_current_user)
):
    """
    Get the activity feed for the current user.
    Used for the 'Recent Activity' dashboard widget.
    """
    # This queries the ActivityFeed table, not AuditLog
    return service.activity_repo.recent_for_user(
        user_id=current_user.id, 
        limit=limit
    )