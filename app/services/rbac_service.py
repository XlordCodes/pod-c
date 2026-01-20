# app/services/rbac_service.py
"""
Module: RBAC Service
Context: Pod B - Module 4 (Security)

Business logic for Role-Based Access Control.
Handles role assignment validation and permission enforcement.
"""

from typing import List, Union, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.repos.role_repo import RoleRepo
from app.models.auth import User, Role

class RBACService:
    """
    Service for managing user roles and enforcing access control policies.
    """
    def __init__(self, db: Session, role_repo_cls=RoleRepo):
        """
        Initialize the service with a database session and repository class.
        Dependency injection of the repository class allows for easier testing.
        
        Args:
            db (Session): The active database session.
            role_repo_cls (Type[RoleRepo]): The repository class to use.
        """
        self.db = db
        self.role_repo = role_repo_cls(db)

    def assign_role_by_name(self, user_id: int, role_name: str) -> User:
        """
        Assigns a role to a user based on the role's name.
        
        Args:
            user_id (int): The ID of the user to update.
            role_name (str): The name of the role (e.g., 'admin', 'editor').
            
        Returns:
            User: The updated User object.
            
        Raises:
            HTTPException(404): If the role name does not exist.
            HTTPException(404): If the user does not exist.
        """
        # 1. Lookup Role
        role = self.role_repo.get_by_name(role_name)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role '{role_name}' not found."
            )

        # 2. Assign Role
        # The repo handles the user lookup and persistence
        updated_user = self.role_repo.assign_role_to_user(user_id, role.id)
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found."
            )

        return updated_user

    def has_role(self, user_id: int, required_roles: Union[str, List[str]]) -> bool:
        """
        Checks if a user possesses one of the required roles.
        
        Args:
            user_id (int): The ID of the user to check.
            required_roles (Union[str, List[str]]): A single role name or list of allowed role names.
            
        Returns:
            bool: True if the user has a matching role, False otherwise.
        """
        if isinstance(required_roles, str):
            required_roles = [required_roles]

        # Normalize required roles to lowercase for comparison
        normalized_required = {r.lower() for r in required_roles}

        # Fetch user's assigned role
        user_role = self.role_repo.get_user_role(user_id)
        
        if not user_role:
            return False

        # Check for match
        return user_role.name.lower() in normalized_required

    def enforce_role(self, user_id: int, required_roles: Union[str, List[str]]) -> None:
        """
        Enforces that a user has the required permissions.
        Raises an HTTP 403 exception if validation fails.
        
        Args:
            user_id (int): The ID of the user.
            required_roles (Union[str, List[str]]): Role(s) required to proceed.
            
        Raises:
            HTTPException(403): If the user lacks the required role.
        """
        if not self.has_role(user_id, required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient privileges. Required roles: {required_roles}"
            )