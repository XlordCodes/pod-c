# app/models_status.py
"""
Module: Message Status Model
Context: Pod C - Module 6 (Reliability & Delivery Receipts).
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.models import Base

class MessageStatus(Base):
    """
    Represents the real-time delivery status of a specific WhatsApp message.
    Separated from ChatMessage to allow high-frequency updates without locking the main table.
    """
    __tablename__ = "message_status"

    id = Column(Integer, primary_key=True)

    # Link back to the immutable chat history.
    message_id = Column(Integer, ForeignKey("chat_messages.id"), nullable=False, index=True)

    # The critical status field (pending -> sent -> delivered -> read).
    wa_status = Column(String, nullable=False, default="pending", index=True)

    # Automatic timestamp handling for updates.
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Optional field to store error codes/messages from WhatsApp for debugging.
    last_error = Column(String, nullable=True)