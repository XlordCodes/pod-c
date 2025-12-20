# app/reports/service_report.py
"""
Module: Analytics Reporting Service
Context: Pod C - Module 7 (Analytics).

Provides read-only access to aggregated data for dashboards.
Uses raw SQL queries or Views for efficiency over large datasets.
"""

from sqlalchemy.orm import Session
from sqlalchemy import text

class ReportService:
    def __init__(self, db: Session):
        self.db = db

    def get_kpi_counts(self) -> dict:
        """
        Calculates high-level delivery KPIs (Sent vs Delivered vs Read).
        Returns a dictionary of counts.
        """
        # Aggregates counts directly in the database
        sql = text("""
            SELECT 
                SUM(CASE WHEN wa_status='sent' THEN 1 ELSE 0 END) AS sent,
                SUM(CASE WHEN wa_status='delivered' THEN 1 ELSE 0 END) AS delivered,
                SUM(CASE WHEN wa_status='read' THEN 1 ELSE 0 END) AS read,
                SUM(CASE WHEN wa_status='failed' THEN 1 ELSE 0 END) AS failed
            FROM message_status
        """)
        
        result = self.db.execute(sql).fetchone()
        
        if not result:
            return {"sent": 0, "delivered": 0, "read": 0, "failed": 0}
            
        # Convert SQLAlchemy Row to dictionary
        return dict(result._mapping)

    def get_sentiment_mix(self) -> list[dict]:
        """
        Retrieves sentiment distribution (e.g., 60% Positive, 10% Negative).
        Relies on the 'v_sentiment_mix' view (defined in migrations).
        Falls back to raw query if view doesn't exist.
        """
        try:
            sql = text("SELECT sentiment, COUNT(*) as count FROM chat_messages GROUP BY sentiment")
            results = self.db.execute(sql).fetchall()
            return [{"sentiment": r.sentiment, "count": r.count} for r in results]
        except Exception:
            return []

    def get_avg_response_time(self) -> list[dict]:
        """
        Retrieves average response time metrics.
        Currently a placeholder for the complex Window Function query defined in Module 7.
        """
        # In a real deployment, this queries the 'v_avg_response' materialized view.
        # For MVP, we return an empty list or a mock if the view isn't hydrated.
        try:
            sql = text("SELECT * FROM v_avg_response LIMIT 50")
            results = self.db.execute(sql).fetchall()
            return [dict(r._mapping) for r in results]
        except Exception:
            # View might not exist yet
            return []