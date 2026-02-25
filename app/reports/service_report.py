# app/reports/service_report.py
"""
Module: Analytics Reporting Service
Context: Pod C - Module 7 (Analytics).

Provides read-only access to aggregated data for dashboards.
Uses raw SQL queries for efficiency over large datasets.
"""

import logging
from typing import Dict, List, Any
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

class ReportService:
    def __init__(self, db: Session):
        self.db = db

    def get_kpi_counts(self) -> Dict[str, int]:
        """
        Calculates high-level delivery KPIs (Sent vs Delivered vs Read).
        Targets the 'bulk_messages' table defined in app/models/bulk.py.
        """
        # We use PostgreSQL's FILTER clause for efficient single-pass aggregation
        sql = text("""
            SELECT 
                COUNT(*) FILTER (WHERE status = 'sent') as sent,
                COUNT(*) FILTER (WHERE status = 'delivered') as delivered,
                COUNT(*) FILTER (WHERE status = 'read') as read,
                COUNT(*) FILTER (WHERE status = 'failed') as failed
            FROM bulk_messages
        """)
        
        result = self.db.execute(sql).fetchone()
        
        if not result:
            return {"sent": 0, "delivered": 0, "read": 0, "failed": 0}
            
        # Convert SQLAlchemy Row to dictionary safely
        return dict(result._mapping)

    def get_sentiment_mix(self) -> List[Dict[str, Any]]:
        """
        Retrieves sentiment distribution (e.g., 60% Positive, 10% Negative).
        Targets the 'chat_messages' table from Pod C.
        
        Returns:
            List[Dict[str, Any]]: List of sentiment counts grouped by sentiment type.
        
        Raises:
            SQLAlchemyError: If the database query fails (bubbles up to caller).
        """
        # Querying the actual table directly
        sql = text("""
            SELECT sentiment, COUNT(*) as count 
            FROM chat_messages 
            WHERE sentiment IS NOT NULL 
            GROUP BY sentiment
        """)
        results = self.db.execute(sql).fetchall()
        return [{"sentiment": row.sentiment, "count": row.count} for row in results]

    def get_avg_response_time(self) -> List[Dict[str, Any]]:
        """
        Retrieves average response time metrics.
        Relies on a Materialized View ('v_avg_response') for performance.
        
        Returns:
            List[Dict[str, Any]]: List of average response time records.
        
        Raises:
            SQLAlchemyError: If the database query fails (bubbles up to caller).
        """
        # We limit to 50 to prevent overloading the dashboard if the view is huge
        sql = text("SELECT * FROM v_avg_response LIMIT 50")
        results = self.db.execute(sql).fetchall()
        return [dict(row._mapping) for row in results]
