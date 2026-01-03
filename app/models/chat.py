from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey, func
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base

class Message(Base):
    """
    Legacy Message model for raw storage of manual messages.
    Note: AI-driven chat history is stored in 'ChatMessage' (Module 3).
    """
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=True)

    message_id = Column(String, unique=True, index=True)
    from_number = Column(String, index=True)
    to_number = Column(String, index=True)
    text = Column(Text, nullable=True)
    message_type = Column(String, nullable=True)
    payload = Column(JSON) 
    
    created_at = Column(
        DateTime(timezone=True), 
        server_default=func.now()
    )
    
    contact_id = Column(
        Integer, 
        ForeignKey("contacts.id", ondelete="SET NULL"), 
        nullable=True
    )
    
    contact = relationship("app.models.crm.Contact", back_populates="messages")


class Conversation(Base):
    """
    Represents a threaded conversation with a specific customer number.
    Used to group individual ChatMessages.
    """
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, index=True, nullable=True)

    customer_number = Column(String, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_message_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ChatMessage(Base):
    """
    Represents a single normalized message in a conversation thread.
    Stores NLP metadata (intent, sentiment) and links to the Conversation.
    """
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"))
    
    # Stores the WhatsApp Message ID (wamid) to link status updates.
    message_id = Column(String, unique=True, index=True, nullable=True)

    from_number = Column(String)
    text = Column(Text)
    
    # NLP Metadata (Module 3 & 5)
    language = Column(String, default="unknown")
    intent = Column(String, default="unclassified")
    sentiment = Column(String, default="neutral") 
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships to extensions (defined in app/models/extensions.py)
    # Using string reference to avoid circular import
    embedding_data = relationship(
        "app.models.extensions.MessageEmbedding", 
        back_populates="message", 
        uselist=False
    )