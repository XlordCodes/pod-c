# app/models_reply.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from datetime import datetime, timezone
from app.models import Base

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