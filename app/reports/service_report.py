from sqlalchemy.orm import Session
from sqlalchemy import text

class ReportService:
    """
    Read-only service for fetching analytics and KPIs.
    Uses raw SQL/Views for performance on aggregated data.
    """
    def __init__(self, db: Session):
        self.db = db

    def get_kpi_counts(self):
        """
        Returns a breakdown of message delivery statuses.
        """
        # We query the MessageStatus table we built in Module 6
        sql = text("""
            SELECT 
                SUM(CASE WHEN wa_status='sent' THEN 1 ELSE 0 END) AS sent,
                SUM(CASE WHEN wa_status='delivered' THEN 1 ELSE 0 END) AS delivered,
                SUM(CASE WHEN wa_status='read' THEN 1 ELSE 0 END) AS read,
                SUM(CASE WHEN wa_status='failed' THEN 1 ELSE 0 END) AS failed
            FROM message_status
        """)
        result = self.db.execute(sql).fetchone()
        
        # Handle case where table is empty (returns None)
        if not result:
            return {"sent": 0, "delivered": 0, "read": 0, "failed": 0}
            
        return dict(result._mapping)

    def get_sentiment_mix(self):
        """
        Returns the sentiment distribution from the v_sentiment_mix view.
        """
        sql = text("SELECT * FROM v_sentiment_mix")
        results = self.db.execute(sql).fetchall()
        return [{"sentiment": r.sentiment, "count": r.count} for r in results]

    def get_avg_response_time(self):
        """
        Returns average response times per conversation from v_avg_response view.
        """
        sql = text("SELECT * FROM v_avg_response LIMIT 50")
        results = self.db.execute(sql).fetchall()
        return [dict(r._mapping) for r in results]