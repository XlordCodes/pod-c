# app/core/permissions.py
"""
Module: RBAC Permissions
Context: Pod B - Module 4 (Security)

Provides dependencies to enforce Role-Based Access Control on API endpoints.
"""

from fastapi import Depends, HTTPException, status
from typing import List, Union

from app.authentication.router import get_current_user
from app.models.auth import User

class RoleChecker:
    """
    Dependency to restrict access to specific roles.
    Usage: @router.get("/", dependencies=[Depends(require_role(["admin", "manager"]))])
    """
    def __init__(self, allowed_roles: Union[str, List[str]]):
        if isinstance(allowed_roles, str):
            self.allowed_roles = [allowed_roles]
        else:
            self.allowed_roles = allowed_roles

    def __call__(self, user: User = Depends(get_current_user)):
        """
        Executable dependency that checks the user's role.
        """
        # 1. Check if user has a role assigned
        if not user.role or not user.role.name:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User has no assigned role."
            )

        # 2. Check if role matches allowed list
        # We normalize to lowercase for comparison
        user_role = user.role.name.lower()
        if user_role not in [r.lower() for r in self.allowed_roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted. Required roles: {self.allowed_roles}"
            )
        
        return True

def require_role(roles: Union[str, List[str]]):
    """
    Helper function to instantiate the RoleChecker.
    """
    return RoleChecker(roles)

def require_admin():
    """Short-hand for admin-only routes."""
    return RoleChecker(["admin"])