# app/models.py
"""
Module: Core Database Models
Context: Pod A (Foundations) & Pod C (Integrations/AI).

This file contains the primary entity definitions for the CRM.
It uses SQLAlchemy ORM to map Python classes to PostgreSQL tables.
"""

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, JSON, ForeignKey, func
)
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime, timezone

# --- CIRCULAR IMPORT FIX ---
# Do NOT import extension models (MessageStatus, etc.) here at the top.
# They rely on 'Base', which is defined below. 
# We will import them at the VERY BOTTOM of this file.
# ---------------------------

# A single, shared Base for all models in the application.
Base = declarative_base()


class User(Base):
    """
    Represents an authenticated system user (e.g., an employee or admin).
    Context: Pod A - Module 1 & 2.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    
    # Timezone-aware timestamp (Python-side default)
    created_at = Column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    contacts = relationship(
        "Contact", 
        back_populates="owner", 
        cascade="all, delete-orphan"
    )


class Contact(Base):
    """
    Represents an external customer or lead managed by a User.
    Context: Pod A - Module 1.
    """
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True, unique=True, index=True)
    phone = Column(String, nullable=True, index=True)
    
    # Server-side default ensures DB consistency
    created_at = Column(
        DateTime(timezone=True), 
        server_default=func.now()
    )
    
    owner_id = Column(
        Integer, 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )

    # Relationships
    owner = relationship("User", back_populates="contacts")
    messages = relationship(
        "Message", 
        back_populates="contact", 
        cascade="all, delete-orphan"
    )


class Message(Base):
    """
    Legacy Message model for raw storage.
    Context: Pod C - Module 1.
    Note: Newer AI features use 'ChatMessage' instead.
    """
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
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
    
    contact = relationship("Contact", back_populates="messages")


# -------------------------
# Bulk Job Models (Module 2)
# -------------------------
class BulkJob(Base):
    """
    Represents a bulk messaging campaign.
    Context: Pod C - Module 2.
    """
    __tablename__ = "bulk_jobs"

    id = Column(Integer, primary_key=True)
    template_name = Column(String, nullable=False)
    language_code = Column(String, nullable=False, default="en_US")
    components = Column(JSON, nullable=True) # Stores template variables
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status = Column(String, default="queued")  # queued, running, done, failed

    messages = relationship("BulkMessage", back_populates="job")


class BulkMessage(Base):
    """
    Represents a single message within a bulk job.
    Context: Pod C - Module 2.
    """
    __tablename__ = "bulk_messages"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("bulk_jobs.id"), nullable=False, index=True)
    to_number = Column(String, index=True)
    status = Column(String, default="pending")  # pending, sent, failed
    attempts = Column(Integer, default=0)
    last_error = Column(String)
    payload = Column(JSON)

    job = relationship("BulkJob", back_populates="messages")


# -------------------------
# Chat & NLP Models (Module 3 & 6)
# -------------------------
class Conversation(Base):
    """
    Represents a threaded conversation with a specific customer number.
    Context: Pod C - Module 3.
    """
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True)
    customer_number = Column(String, index=True)
    last_message_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ChatMessage(Base):
    """
    Represents a single normalized message in a conversation thread.
    Context: Pod C - Module 3, 4, 5, 6.
    """
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"))
    
    # Stores the WhatsApp Message ID (wamid) to link status updates.
    message_id = Column(String, unique=True, index=True, nullable=True)
    # -----------------------------

    from_number = Column(String)
    text = Column(Text)
    
    # NLP Metadata (Module 3 & 5)
    language = Column(String, default="unknown")
    intent = Column(String, default="unclassified")
    sentiment = Column(String, default="neutral") 
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

# ---------------------------------------------------------
# IMPORT EXTENSION MODELS AT THE BOTTOM
# ---------------------------------------------------------
# This allows 'Base' to be fully defined above BEFORE these 
# modules try to import it. This resolves the Circular Import error.
# Alembic needs these imports here to 'see' the new tables.
from app.models_status import MessageStatus
from app.models_vector import MessageEmbedding
from app.models_reply import ReplySuggestion