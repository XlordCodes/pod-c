# app/models/auth.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base

class Role(Base):
    """
    Defines user roles for RBAC (e.g., Admin, Manager, Staff).
    """
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)  # e.g., "admin", "staff"
    
    # --- ADDED FIELD ---
    description = Column(String, nullable=True) 

    users = relationship("User", back_populates="role")


class User(Base):
    """
    Represents an authenticated system user.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)
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