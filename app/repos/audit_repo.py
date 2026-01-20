# app/repos/audit_repo.py
"""
Module: Audit & Activity Repositories
Context: Pod B - Data Access Layer

Handles the persistence and efficient retrieval of Audit Logs and Activity Feeds.
Strictly enforcing read/write patterns (Audits are typically append-only).
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.audit import AuditLog, ActivityFeed

class AuditRepo:
    """
    Repository for managing system compliance logs.
    """
    def __init__(self, db: Session):
        self.db = db

    def add_log(self, log: AuditLog) -> AuditLog:
        """
        Persists a new audit log entry to the database.
        """
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def list_logs(
        self, 
        entity: Optional[str] = None, 
        entity_id: Optional[int] = None, 
        actor_id: Optional[int] = None,
        limit: int = 50,
        skip: int = 0
    ) -> List[AuditLog]:
        """
        Retrieves a paginated list of audit logs based on filters.
        """
        query = self.db.query(AuditLog)

        if entity:
            query = query.filter(AuditLog.entity == entity)
        
        if entity_id:
            query = query.filter(AuditLog.entity_id == entity_id)
            
        if actor_id:
            query = query.filter(AuditLog.actor_id == actor_id)
        
        return (
            query.order_by(desc(AuditLog.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )


class ActivityRepo:
    """
    Repository for managing user activity feeds.
    """
    def __init__(self, db: Session):
        self.db = db

    def add(self, activity: ActivityFeed) -> ActivityFeed:
        """
        Persists a new activity feed item.
        """
        self.db.add(activity)
        self.db.commit()
        self.db.refresh(activity)
        return activity

    def recent_for_user(self, user_id: int, limit: int = 20) -> List[ActivityFeed]:
        """
        Fetches the most recent activity items for a specific user.
        """
        return (
            self.db.query(ActivityFeed)
            .filter(ActivityFeed.user_id == user_id)
            .order_by(desc(ActivityFeed.created_at))
            .limit(limit)
            .all()
        )