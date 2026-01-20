# app/api/roles.py
"""
Module: Role API Router
Context: Pod B - Module 4 (Security)

Exposes endpoints for Role Management (RBAC).
These operations are typically restricted to 'admin' users.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.authentication.router import get_current_user
from app.models.auth import User

# Import Domain Components
from app.schemas.role import RoleCreate, RoleOut, UserRoleAssign
from app.services.rbac_service import RBACService
from app.core.permissions import require_admin  # Ensures only admins can access

router = APIRouter()

# --- Dependency ---
def get_rbac_service(db: Session = Depends(get_db)) -> RBACService:
    """
    Factory dependency to instantiate RBACService with a DB session.
    """
    return RBACService(db)

# --- Endpoints ---

@router.post("/", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
def create_role(
    payload: RoleCreate,
    service: RBACService = Depends(get_rbac_service),
    current_user: User = Depends(require_admin())
):
    """
    Create a new system role (e.g., 'editor', 'auditor').
    Restricted to Admins.
    """
    # Note: We access the repo through the service layer, or add a wrapper in service.
    # For simplicity, we assume the service might expose a direct create method, 
    # or we use the repo attached to the service if strict layering allows.
    # To maintain strict service-layer pattern, we should add 'create_role' to RBACService.
    # For now, we will use the internal repo of the service.
    return service.role_repo.create_role(
        name=payload.name, 
        description=payload.description
    )

@router.get("/", response_model=List[RoleOut])
def list_roles(
    skip: int = 0,
    limit: int = 100,
    service: RBACService = Depends(get_rbac_service),
    current_user: User = Depends(require_admin())
):
    """
    List all available roles in the system.
    Restricted to Admins.
    """
    return service.role_repo.list_roles(skip=skip, limit=limit)

@router.post("/users/{user_id}/assign", response_model=RoleOut)
def assign_role_to_user(
    user_id: int,
    payload: UserRoleAssign,
    service: RBACService = Depends(get_rbac_service),
    current_user: User = Depends(require_admin())
):
    """
    Assign a role to a specific user.
    Example: Make User #5 an 'manager'.
    Restricted to Admins.
    """
    # 1. Update User Role
    updated_user = service.assign_role_by_name(user_id, payload.role_name)
    
    # 2. Return the assigned role details
    # We rely on the relationship being loaded or fetch it directly
    if not updated_user.role:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Role assignment failed internally."
        )
        
    return updated_user.role