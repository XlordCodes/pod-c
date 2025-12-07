# app/models_status.py
"""
Module: Message Status Model
Context: Pod C - Module 6 (Reliability & Delivery Receipts).

This module defines the database schema for tracking the lifecycle of outgoing
WhatsApp messages. It separates the *content* of a message (immutable, stored in
ChatMessages) from its *delivery state* (mutable, updated via webhooks).
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.models import Base

class MessageStatus(Base):
    """
    Represents the real-time delivery status of a specific WhatsApp message.

    Design Decision:
    We use a separate table for status rather than updating the 'ChatMessage' table
    to keep the chat history immutable and performant. This table is optimized for
    high-frequency updates (UPSERTS) from webhooks.

    Attributes:
        id (int): Primary Key.
        message_id (int): Foreign Key linking to the core 'chat_messages' table.
        wa_status (str): The current delivery state (e.g., 'sent', 'delivered', 'read', 'failed').
                         Indexed for fast dashboard analytics.
        updated_at (datetime): The timestamp of the last status change. managed by the DB.
        last_error (str): Stores raw error text from Meta if the message failed.
    """
    __tablename__ = "message_status"

    id = Column(Integer, primary_key=True)

    # Link back to the immutable chat history.
    # Note: Ensure 'chat_messages.id' exists in your schema (Module 3).
    message_id = Column(Integer, ForeignKey("chat_messages.id"), nullable=False, index=True)

    # The critical status field.
    # Valid values usually flow: pending -> sent -> delivered -> read
    wa_status = Column(String, nullable=False, default="pending", index=True)

    # Automatic timestamp handling.
    # server_default=func.now() sets it on creation.
    # onupdate=func.now() updates it automatically whenever the row changes.
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Optional field to store error codes/messages from WhatsApp for debugging.
    last_error = Column(String, nullable=True)