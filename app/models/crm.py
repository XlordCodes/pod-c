# app/models/crm.py
"""
Module: CRM Domain Models
Context: Pod B - Business Logic (Leads, Deals, Contacts)

Defines the core entities for the Customer Relationship Management system.
Includes:
- Contact: Established customers (Pod A legacy support).
- Lead: Potential customers (Module 1).
- Deal: Sales opportunities linked to Leads (Module 1).
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base
from app.core.security import encrypt_value, decrypt_value

class Contact(Base):
    """
    Represents an external customer or lead managed by a User.
    Maintained for compatibility with existing Pod A architecture.
    """
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=True) # Logical isolation
    
    name = Column(String, nullable=False)
    email = Column(String, nullable=True, unique=True, index=True)
    phone = Column(String, nullable=True, unique=True, index=True)
    
    # Stores dynamic attributes like 'segment', 'source', 'preferences'
    custom_fields = Column(JSON, default={}) 

    # Module 5: Encrypted Field
    _national_id = Column("national_id", String, nullable=True)

    @property
    def national_id(self):
        """Returns the decrypted value when accessed via python."""
        return decrypt_value(self._national_id)

    @national_id.setter
    def national_id(self, value):
        """Encrypts the value automatically when setting."""
        self._national_id = encrypt_value(value)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    owner_id = Column(
        Integer, 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )

    # Relationships
    owner = relationship("app.models.auth.User", back_populates="contacts")
    
    messages = relationship(
        "app.models.chat.Message", 
        back_populates="contact", 
        cascade="all, delete-orphan"
    )

    invoices = relationship(
        "app.models.finance.Invoice",
        back_populates="contact"
    )


class Lead(Base):
    """
    Represents a potential customer before qualification.
    Tracks the early stage of the sales pipeline.
    """
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    
    name = Column(String, nullable=False)
    email = Column(String, nullable=True, index=True)
    status = Column(String, default="new", index=True) # new, contacted, qualified, converted
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Ownership for RBAC
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Relationships
    owner = relationship("app.models.auth.User")
    deals = relationship("Deal", back_populates="lead", cascade="all, delete-orphan")


class Deal(Base):
    """
    Represents a sales opportunity associated with a Lead.
    Tracks financial value and pipeline progress.
    """
    __tablename__ = "deals"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    
    # Link to Lead (One-to-Many: One Lead can have multiple Deals)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    
    # Financials (Stored as integers to prevent floating point errors)
    value_cents = Column(Integer, nullable=False, default=0)
    
    # Sales attribution
    seller_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    lead = relationship("Lead", back_populates="deals")
    seller = relationship("app.models.auth.User", foreign_keys=[seller_id])