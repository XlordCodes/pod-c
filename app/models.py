# app/models.py
from sqlalchemy import (
    Column, Integer, String, Text,  DateTime, JSON, ForeignKey, func
)
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime, timezone
 
# A single, shared Base for all models in the application.
Base = declarative_base()


class User(Base):
    """
    Represents an authenticated user in the system.
    Each user can own multiple contacts.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )

    # Establishes the one-to-many relationship from User to Contact.
    # The `cascade="all, delete-orphan"` ensures that when a User is deleted,
    # all of their associated Contacts are also deleted.
    contacts = relationship(
        "Contact", 
        back_populates="owner", 
        cascade="all, delete-orphan"
    )


class Contact(Base):
    """
    Represents a contact, which must be owned by a User.
    A contact can be associated with multiple messages.
    """
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True, unique=True, index=True)
    phone = Column(String, nullable=True, index=True)
    created_at = Column(
        DateTime(timezone=True), 
        server_default=func.now()
    )
    
    # Foreign key to link this contact to its owner in the 'users' table.
    # This field is non-nullable, enforcing that every contact has an owner.
    owner_id = Column(
        Integer, 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )

    # Establishes the many-to-one relationship from Contact to User.
    owner = relationship("User", back_populates="contacts")
    
    # Establishes the one-to-many relationship from Contact to Message.
    messages = relationship(
        "Message", 
        back_populates="contact", 
        cascade="all, delete-orphan"
    )


class Message(Base):
    """
    Represents a message sent to or from a Contact.
    """
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String, unique=True, index=True)
    from_number = Column(String, index=True)
    to_number = Column(String, index=True)
    text = Column(Text, nullable=True)
    message_type = Column(String, nullable=True)
    payload = Column(JSON) # Stores the raw webhook payload for debugging/auditing.
    created_at = Column(
        DateTime(timezone=True), 
        server_default=func.now()
    )
    
    # Foreign key to link this message to a contact. Can be nullable if some
    # messages are not immediately associated with a known contact.
    contact_id = Column(
        Integer, 
        ForeignKey("contacts.id", ondelete="SET NULL"), 
        nullable=True
    )
    
    # Establishes the many-to-one relationship from Message to Contact.
    contact = relationship("Contact", back_populates="messages")

# -------------------------
# Bulk Job Model
# -------------------------
class BulkJob(Base):
    __tablename__ = "bulk_jobs"

    id = Column(Integer, primary_key=True)
    template_name = Column(String, nullable=False) # Renamed from 'template'
    language_code = Column(String, nullable=False, default="en_US") # New
    components = Column(JSON, nullable=True) # New (for template parameters/components)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status = Column(String, default="queued")  # queued, running, done, failed

    messages = relationship("BulkMessage", back_populates="job")

# -------------------------
# Bulk Message Model
# -------------------------
class BulkMessage(Base):
    __tablename__ = "bulk_messages"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("bulk_jobs.id"), nullable=False, index=True)
    to_number = Column(String, index=True)
    status = Column(String, default="pending")  # pending, sent, failed
    attempts = Column(Integer, default=0)
    last_error = Column(String)
    payload = Column(JSON) # Optional: to store the exact payload sent

    # Relationship
    job = relationship("BulkJob", back_populates="messages")

# -------------------------
# Conversation and ChatMessage Models
# -------------------------
class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True)
    customer_number = Column(String, index=True)
    last_message_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))    
    # Note: Relationships (like messages) are added by the subsequent class or later.

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"))
    from_number = Column(String)
    text = Column(Text)
    language = Column(String, default="unknown")
    intent = Column(String, default="unclassified")
    # Fix: Add Sentiment Column (Module 5 requirement)
    sentiment = Column(String, default="neutral") 
    
    # Fix: Use timezone-aware default
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))