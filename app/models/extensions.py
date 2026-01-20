# app/models/extensions.py
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

    id = Column(Integer, primary_key=True)

    # Link back to the immutable chat history.
    message_id = Column(Integer, ForeignKey("chat_messages.id"), nullable=False, index=True)

    # The critical status field (pending -> sent -> delivered -> read).
    wa_status = Column(String, nullable=False, default="pending", index=True)

    # Automatic timestamp handling for updates.
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Optional field to store error codes/messages from WhatsApp for debugging.
    last_error = Column(String, nullable=True)

    # --- ADDED RELATIONSHIP ---
    # This matches: ChatMessage.statuses = relationship(..., back_populates="message")
    message = relationship(
        "app.models.chat.ChatMessage",
        back_populates="statuses"
    )


class MessageEmbedding(Base):
    """
    Stores vector embeddings for ChatMessages to enable semantic search.
    Requires the 'pgvector' extension in PostgreSQL.
    """
    __tablename__ = "message_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("chat_messages.id"), unique=True, nullable=False)
    
    # 1024 dimensions match the Cohere embed-english-v3.0 model
    embedding = Column(Vector(1024)) 
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationship to the parent message
    message = relationship(
        "app.models.chat.ChatMessage", 
        back_populates="embedding_data"
    )


class ReplySuggestion(Base):
    """
    Stores AI-generated reply suggestions for a specific chat message.
    Used by the frontend to assist agents.
    """
    __tablename__ = "reply_suggestions"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("chat_messages.id"))
    suggestion = Column(Text)
    rank = Column(Integer)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # --- ADDED RELATIONSHIP ---
    # This matches: ChatMessage.suggestions = relationship(..., back_populates="message")
    message = relationship(
        "app.models.chat.ChatMessage",
        back_populates="suggestions"
    )