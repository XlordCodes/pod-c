# app/models/chat.py
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey, func
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base

# NOTE: Do NOT import other models here (like MessageEmbedding) to avoid circular imports.
# Use string references in relationship() calls instead.

class Message(Base):
    """
    Legacy Message model for raw storage of manual messages.
    Maintained for backward compatibility with non-AI message flows.
    """
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=True)

    # Unique WhatsApp Message ID (wamid)
    message_id = Column(String, unique=True, index=True)
    from_number = Column(String, index=True)
    to_number = Column(String, index=True)
    text = Column(Text, nullable=True)
    message_type = Column(String, nullable=True) # text, image, template, etc.
    payload = Column(JSON) 
    
    created_at = Column(
        DateTime(timezone=True), 
        server_default=func.now()
    )
    
    # Link to CRM Contact (Optional)
    contact_id = Column(
        Integer, 
        ForeignKey("contacts.id", ondelete="SET NULL"), 
        nullable=True
    )
    
    # Relationship using string reference
    contact = relationship("app.models.crm.Contact", back_populates="messages")


class Conversation(Base):
    """
    Represents a threaded conversation with a specific customer number.
    Used to group individual ChatMessages for the UI and AI context.
    """
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, index=True, nullable=True)

    customer_number = Column(String, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Updated whenever a new message is received; used for sorting in UI
    last_message_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ChatMessage(Base):
    """
    Represents a single normalized message in a conversation thread.
    Stores NLP metadata (intent, sentiment) and links to Vector Embeddings.
    """
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"))
    
    # Stores the WhatsApp Message ID (wamid) to link status updates & embeddings
    message_id = Column(String, unique=True, index=True, nullable=True)

    from_number = Column(String)
    text = Column(Text)
    
    # NLP Metadata (populated by SimpleNLPService & SentimentService)
    language = Column(String, default="unknown")
    intent = Column(String, default="unclassified")
    sentiment = Column(String, default="neutral") 
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # --- Relationships ---
    
    # 1. Vector Embeddings (One-to-One)
    # Defined in app/models/extensions.py
    embedding_data = relationship(
        "app.models.extensions.MessageEmbedding", 
        back_populates="message", 
        uselist=False,
        cascade="all, delete-orphan"
    )

    # 2. Delivery Status (One-to-Many, usually just one current status)
    # Defined in app/models/extensions.py
    statuses = relationship(
        "app.models.extensions.MessageStatus",
        back_populates="message",
        cascade="all, delete-orphan"
    )

    # 3. AI Reply Suggestions (One-to-Many)
    # Defined in app/models/extensions.py
    suggestions = relationship(
        "app.models.extensions.ReplySuggestion",
        back_populates="message",
        cascade="all, delete-orphan"
    )