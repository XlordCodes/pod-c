# app/models/extensions.py
"""
Module: Data Extensions
Context: Pod C - AI & Metadata

Defines satellite tables that extend the core chat functionality.
- MessageStatus: Real-time WhatsApp delivery updates (detached for performance).
- MessageEmbedding: Vector storage for RAG/Semantic Search.
- ReplySuggestion: AI-generated draft responses.
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from datetime import datetime, timezone
from app.database import Base

class MessageStatus(Base):
    """
    Represents the real-time delivery status of a specific WhatsApp message.
    Separated from ChatMessage to allow high-frequency updates without locking the main table.
    """
    __tablename__ = "message_status"

    id = Column(Integer, primary_key=True, index=True)

    # Link back to the immutable chat history.
    message_id = Column(Integer, ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False, index=True)

    # The critical status field (pending -> sent -> delivered -> read).
    wa_status = Column(String, nullable=False, default="pending", index=True)

    # Automatic timestamp handling for updates.
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Optional field to store error codes/messages from WhatsApp for debugging.
    last_error = Column(String, nullable=True)

    # Relationships
    message = relationship(
        "ChatMessage",
        back_populates="statuses"
    )


class MessageEmbedding(Base):
    """
    Stores vector embeddings for ChatMessages to enable semantic search.
    Requires the 'pgvector' extension in PostgreSQL.
    """
    __tablename__ = "message_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("chat_messages.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    # [CRITICAL UPDATE] 
    # OpenAI 'text-embedding-3-small' uses 1536 dimensions.
    # Previous Cohere model used 1024.
    embedding = Column(Vector(1536)) 
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationship to the parent message
    message = relationship(
        "ChatMessage", 
        back_populates="embedding_data"
    )


class ReplySuggestion(Base):
    """
    Stores AI-generated reply suggestions for a specific chat message.
    Used by the frontend to assist agents.
    """
    __tablename__ = "reply_suggestions"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("chat_messages.id", ondelete="CASCADE"))
    
    suggestion = Column(Text)
    rank = Column(Integer, default=1)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationship
    message = relationship(
        "ChatMessage",
        back_populates="suggestions"
    )