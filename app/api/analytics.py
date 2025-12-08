from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.reports.service_report import ReportService

router = APIRouter(prefix="/analytics", tags=["Analytics & BI"])

@router.get("/kpis")
def get_kpis(db: Session = Depends(get_db)):
    """Get high-level delivery KPIs (Sent, Read, Failed)."""
    return ReportService(db).get_kpi_counts()

@router.get("/sentiment")
def get_sentiment(db: Session = Depends(get_db)):
    """Get sentiment distribution across all chats."""
    return ReportService(db).get_sentiment_mix()

@router.get("/response-time")
def get_response_time(db: Session = Depends(get_db)):
    """Get average response time (in minutes) per conversation."""
    return ReportService(db).get_avg_response_time()