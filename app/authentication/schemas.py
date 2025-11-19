from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

# =================================
#       USER SCHEMAS
# =================================

# --- User Base Schema ---
# Shared properties for a user.
class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None

# --- User Create Schema ---
# Properties required when creating a new user (e.g., via /register).
# Inherits from UserBase and adds the password.
class UserCreate(UserBase):
    password: str

# --- User Schema ---
# Properties to be returned from the API when fetching a user.
# IMPORTANT: It does NOT include the password for security.
class User(UserBase):
    id: int
    created_at: datetime

    class Config:
        # This allows Pydantic to read the data from an ORM object (SQLAlchemy)
        from_attributes = True


# =================================
#       TOKEN SCHEMAS
# =================================

# --- Token Schema ---
# The shape of the response when a user successfully logs in.
class Token(BaseModel):
    access_token: str
    token_type: str

# --- Token Data Schema ---
# The shape of the data encoded within the JWT access token.
class TokenData(BaseModel):
    email: Optional[str] = None
