# app/models/bulk.py
"""
Module: Bulk Messaging Models
Context: Pod C - Marketing & Broadcasts

Defines entities for high-volume messaging jobs.
- BulkJob: The parent container for a broadcast campaign.
- BulkMessage: Individual message status tracking.
- EmailQueue: Persistent queue for transactional emails.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base

class BulkJob(Base):
    """
    Represents a broadcast campaign (e.g., "Holiday Sale Alert").
    """
    __tablename__ = "bulk_jobs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=False) # Security Boundary

    template_name = Column(String, nullable=False)
    language_code = Column(String, default="en_US")
    
    # Status: 'queued', 'scheduled', 'running', 'completed', 'failed'
    status = Column(String, default="queued", index=True)
    
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Template variables (e.g., Header image, dynamic text)
    components = Column(JSON, default=list)

    # Relationships
    messages = relationship("BulkMessage", back_populates="job", cascade="all, delete-orphan")


class BulkMessage(Base):
    """
    Represents a single message within a Job.
    Used for tracking individual delivery status and retries.
    """
    __tablename__ = "bulk_messages"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("bulk_jobs.id", ondelete="CASCADE"), nullable=False)
    
    to_number = Column(String, nullable=False, index=True)
    
    # Status: 'pending', 'sent', 'failed'
    status = Column(String, default="pending", index=True)
    
    # External ID from WhatsApp (WAMID) for tracking read receipts later
    whatsapp_message_id = Column(String, nullable=True, index=True)
    
    attempts = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    
    job = relationship("BulkJob", back_populates="messages")


class EmailQueue(Base):
    """
    Persistent queue for transactional emails.
    Decouples the API from the SMTP server to handle spikes/failures.
    """
    __tablename__ = "email_queue"

    id = Column(Integer, primary_key=True, index=True)
    # Note: If email needs multi-tenancy later, add tenant_id here.
    
    to_email = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    template_name = Column(String, nullable=False)
    context = Column(JSON, nullable=True)
    
    status = Column(String, default="pending", index=True)
    attempts = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())