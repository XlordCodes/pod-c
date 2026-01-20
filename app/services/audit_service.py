# app/services/audit_service.py
"""
Module: Audit Service
Context: Pod B - Module 3 (Business Logic)

Central service for recording system events.
Correctly maps 'actor_id' (User ID) to the AuditLog model.
"""

from sqlalchemy.orm import Session
from typing import Dict, Any, Optional

from app.models.audit import AuditLog, ActivityFeed
from app.repos.audit_repo import AuditRepo, ActivityRepo

# Import context helpers
try:
    from app.core.context import get_request_id
except ImportError:
    def get_request_id(): return None

class AuditService:
    def __init__(self, db: Session):
        # We initialize Repos directly here to ensure they are available
        self.db = db
        self.audit_repo = AuditRepo(db)
        self.activity_repo = ActivityRepo(db)

    def log_event(
        self, 
        actor_id: Optional[int], 
        entity: str, 
        entity_id: int, 
        action: str, 
        changes: Dict[str, Any] = None,
        meta: Dict[str, Any] = None
    ) -> AuditLog:
        """
        Records a compliance event.
        """
        final_meta = meta or {}
        
        # Auto-inject Trace ID
        trace_id = get_request_id()
        if trace_id:
            final_meta["trace_id"] = trace_id

        # --- CRITICAL MAPPING ---
        # The Model expects 'actor_id', NOT 'user_id'.
        log = AuditLog(
            actor_id=actor_id,   # <--- Correct Field Name
            entity=entity,
            entity_id=entity_id,
            action=action,
            changes=changes or {},
            meta=final_meta
        )
        return self.audit_repo.add_log(log)

    def post_activity(self, user_id: int, message: str, category: str = "general") -> ActivityFeed:
        """
        Posts a user-facing activity message.
        """
        # --- CRITICAL MAPPING ---
        # The ActivityFeed Model expects 'user_id'.
        feed = ActivityFeed(
            user_id=user_id,     
            message=message, 
            category=category
        )
        return self.activity_repo.add(feed)