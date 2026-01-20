# app/api/analytics.py
"""
Module: Analytics & BI API
Context: Pod C - Module 7 (Reporting).

Exposes read-only endpoints for high-level business metrics.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.reports.service_report import ReportService
from app.models import User
from app.authentication.router import get_current_user

router = APIRouter()

@router.get("/kpis")
def get_kpis(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get high-level delivery KPIs (Sent/Delivered/Read/Failed counts).
    """
    return ReportService(db).get_kpi_counts()

@router.get("/sentiment")
def get_sentiment(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get the distribution of sentiment across all messages.
    Useful for pie charts.
    """
    return ReportService(db).get_sentiment_mix()

@router.get("/avg-response")
def get_response_time(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get average response time metrics per conversation.
    """
    return ReportService(db).get_avg_response_time()