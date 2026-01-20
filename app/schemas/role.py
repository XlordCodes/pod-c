# app/schemas/role.py
"""
Module: Role Schemas
Context: Pod B - Module 4 (Security)

Defines Pydantic data transfer objects (DTOs) for Role management.
Ensures strict validation for role creation and assignment payloads.
"""

from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

class RoleBase(BaseModel):
    """
    Shared properties for Role models.
    """
    name: str = Field(
        ..., 
        min_length=2, 
        max_length=50, 
        description="Unique identifier for the role (e.g., 'admin', 'manager')."
    )
    description: Optional[str] = Field(
        None, 
        max_length=255, 
        description="Human-readable description of the permissions associated with this role."
    )

class RoleCreate(RoleBase):
    """
    Payload for creating a new system role.
    Inherits validation from RoleBase.
    """
    pass

class RoleOut(RoleBase):
    """
    Response schema for Role details.
    """
    id: int

    model_config = ConfigDict(from_attributes=True)

class UserRoleAssign(BaseModel):
    """
    Payload for assigning a role to a specific user.
    """
    role_name: str = Field(
        ..., 
        description="The exact name of the role to assign (case-insensitive)."
    )