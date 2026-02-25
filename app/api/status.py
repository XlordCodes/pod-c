# app/api/status.py
"""
Module: Reliability Dashboard API
Context: Pod C - Module 6 (Ops/Reliability).

Provides visibility into message delivery rates.
Intended for internal dashboards (e.g., Grafana or Admin UI).

SECURITY: All endpoints require JWT authentication.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.status_service import StatusService
from app.models import MessageStatus
from app.authentication.router import get_current_user
from app.models.auth import User

router = APIRouter()

@router.get("/summary")
def status_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get aggregate counts of message statuses (sent, delivered, read, failed).
    
    SECURITY: Requires valid JWT authentication.
    
    Args:
        db (Session): Database session dependency.
        current_user (User): The authenticated user making the request.
        
    Returns:
        dict: Aggregate message status metrics.
    """
    svc = StatusService(db)
    return svc.get_metrics()

@router.get("/message/{msg_id}")
def message_status(
    msg_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get the detailed delivery status for a specific message ID.
    
    SECURITY: Requires valid JWT authentication.
    
    Args:
        msg_id (int): The message ID to query.
        db (Session): Database session dependency.
        current_user (User): The authenticated user making the request.
        
    Returns:
        dict: Message status details including status, errors, and timestamp.
        
    Raises:
        HTTPException 404: If status not found for the message.
    """
    # Direct query here is fine as it's a simple read
    row = db.query(MessageStatus).filter_by(message_id=msg_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Status not found for this message")
    
    return {
        "message_id": msg_id, 
        "status": row.wa_status,
        "last_error": row.last_error,
        "updated_at": row.updated_at
    }
