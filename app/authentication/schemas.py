# app/authentication/schemas.py
from pydantic import BaseModel, EmailStr, ConfigDict
from datetime import datetime
from typing import Optional

class UserBase(BaseModel):
    """
    Shared properties for user input/output.
    """
    email: EmailStr
    name: Optional[str] = None

class UserCreate(UserBase):
    """
    Payload for registering a new user.
    
    SECURITY: tenant_id and role_id are intentionally excluded from public input
    to prevent IDOR and privilege escalation vulnerabilities. Tenant and role
    assignment is deferred to a secure workspace creation/invitation flow.
    """
    password: str
    company_name: Optional[str] = None

class User(UserBase):
    """
    Public User profile (excludes password).
    """
    id: int
    created_at: datetime
    tenant_id: Optional[int] = None
    role_id: Optional[int] = None

    # Modern Pydantic V2 configuration for ORM compatibility
    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    """
    JWT Token response structure.
    """
    access_token: str
    token_type: str

class TokenData(BaseModel):
    """
    Data embedded in the JWT payload.
    """
    email: Optional[str] = None