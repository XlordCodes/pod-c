# app/models/auth.py
"""
Module: Authentication Models
Context: Pod A - Identity & Access Management

Defines:
- User: The authenticated entity.
- Role: RBAC definitions (Scoped per Tenant).

Security Note:
- User emails are globally unique to simplify the login process (1 User = 1 Identity).
- Roles are scoped to Tenants to allow custom permission sets per organization.
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base

class Role(Base):
    """
    Defines user roles for RBAC (e.g., Admin, Manager, Staff).
    Scoped to a specific Tenant to allow for custom roles.
    """
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=True) # Nullable for potential Global System Roles
    
    name = Column(String, nullable=False) 
    description = Column(String, nullable=True) 

    users = relationship("User", back_populates="role")

    __table_args__ = (
        UniqueConstraint('tenant_id', 'name', name='uq_role_tenant_name'),
    )


class User(Base):
    """
    Represents an authenticated system user.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)
    
    # Global Uniqueness on Email simplifies the Login flow (No need to ask "Which Workspace?").
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    
    # RBAC & Multi-Tenancy
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=True)
    tenant_id = Column(Integer, index=True, nullable=True)

    created_at = Column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    role = relationship("Role", back_populates="users")
    
    contacts = relationship(
        "app.models.crm.Contact", 
        back_populates="owner", 
        cascade="all, delete-orphan"
    )