# app/models/audit.py
"""
Module: Audit & Activity Models
Context: Pod B - Module 3 (Audit Trails)

Defines the core entities for tracking system changes and user activity.
1. AuditLog: An immutable, append-only record of system events (Compliance).
2. ActivityFeed: A timeline of user-centric notifications (User Experience).
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base

class AuditLog(Base):
    """
    Represents a single immutable record of an action performed on a system entity.
    Used for compliance, security auditing, and debugging history.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    
    # Actor: The user who performed the action. 
    # Nullable because some actions are performed by the system (e.g., automated billing).
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    
    # Entity: The type of resource being modified (e.g., "Invoice", "Lead", "InventoryItem").
    entity = Column(String, nullable=False, index=True)
    
    # Entity ID: The primary key of the specific resource.
    entity_id = Column(Integer, nullable=True, index=True)
    
    # Action: A short verb describing the event (e.g., "create", "update", "delete", "promote").
    action = Column(String, nullable=False, index=True)
    
    # Changes: A JSON snapshot of the state change.
    # Recommended format: {"field_name": {"old": value, "new": value}}
    changes = Column(JSON, nullable=True)
    
    # Metadata: Additional context like IP address, User-Agent, or Request ID.
    meta = Column(JSON, default={})
    
    # Timestamp: Server-side generated UTC timestamp.
    created_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        index=True
    )

    # Relationships
    actor = relationship("app.models.auth.User")


class ActivityFeed(Base):
    """
    Represents a user-facing activity item.
    These are the "stories" shown on a dashboard (e.g., "John updated Invoice #102").
    """
    __tablename__ = "activity_feed"

    id = Column(Integer, primary_key=True, index=True)
    
    # User: The specific user this feed item belongs to (or who generated it).
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    
    # Message: A human-readable string describing the activity.
    message = Column(String, nullable=False)
    
    # Category: Optional grouping (e.g., "finance", "crm", "system").
    category = Column(String, default="general", index=True)
    
    # Timestamp: When the activity occurred.
    created_at = Column(
        DateTime(timezone=True), 
        server_default=func.now()
    )

    # Relationships
    user = relationship("app.models.auth.User")