# app/models/communication.py
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base

class BulkJob(Base):
    __tablename__ = "bulk_jobs"

    id = Column(Integer, primary_key=True, index=True)
    
    # --- ADDED FIELD ---
    tenant_id = Column(Integer, index=True, nullable=False)

    template_name = Column(String, nullable=False)
    language_code = Column(String, default="en")
    
    # Status: 'queued', 'scheduled', 'processing', 'completed', 'failed'
    status = Column(String, default="queued")
    
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    components = Column(JSON, default=list)

    # Relationships
    messages = relationship("BulkMessage", back_populates="job")


class BulkMessage(Base):
    __tablename__ = "bulk_messages"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("bulk_jobs.id"))
    to_number = Column(String, nullable=False)
    
    # Status: 'pending', 'sent', 'failed'
    status = Column(String, default="pending")
    whatsapp_message_id = Column(String, nullable=True)
    
    attempts = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    
    job = relationship("BulkJob", back_populates="messages")


class EmailQueue(Base):
    """
    Persistent queue for transactional emails.
    """
    __tablename__ = "email_queue"

    id = Column(Integer, primary_key=True, index=True)
    to_email = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    template_name = Column(String, nullable=False)
    context = Column(JSON, nullable=True)
    
    status = Column(String, default="pending", index=True)
    attempts = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())