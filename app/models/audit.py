from sqlalchemy import Column, Integer, String, DateTime, JSON
from datetime import datetime, timezone
from app.database import Base

class AuditLog(Base):
    """
    Immutable log of critical data changes.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    
    user_id = Column(Integer, index=True, nullable=True)
    target_type = Column(String, index=True) 
    target_id = Column(Integer, index=True)
    action = Column(String) 
    
    state_before = Column(JSON, nullable=True)
    state_after = Column(JSON, nullable=True)
    
    request_id = Column(String, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))