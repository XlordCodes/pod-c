# app/api/status.py
"""
Module: Status Dashboard API
Context: Pod C - Module 6 (Reliability).

This module exposes endpoints to query the delivery health of the messaging system.
It provides aggregated metrics (e.g., "How many messages failed today?") suitable
for admin dashboards.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.status_service import StatusService

# Define the router with a specific prefix and tag for documentation grouping
router = APIRouter(prefix="/status", tags=["Reliability/Dashboard"])

@router.get("/metrics")
def get_delivery_metrics(db: Session = Depends(get_db)):
    """
    Retrieve aggregate delivery metrics for all messages.

    Returns:
        dict: A key-value mapping of statuses to their counts.
              e.g. {"sent": 10, "delivered": 5, "read": 8, "failed": 1}
    """
    svc = StatusService(db)
    return svc.get_metrics()