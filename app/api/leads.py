# app/api/leads.py
"""
Module: Leads API Router
Context: Pod B - Interface Layer (Module 1).

Exposes REST endpoints for managing Leads and promoting them to Deals.
Delegates all business logic to LeadService.

SECURITY CONTROLS:
- Duplicate email detection on create
- Owner validation on create
- State lock on converted leads (cannot edit)
"""

import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

# --- Core Imports ---
from app.database import get_db
from app.authentication.router import get_current_user
from app.models.auth import User

# --- Domain Imports ---
from app.services.lead_service import LeadService
from app.schemas.crm import LeadCreate, LeadUpdate, LeadOut, DealOut

# Initialize Router
router = APIRouter()
logger = logging.getLogger(__name__)

# --- Dependency Injection ---

def get_service(db: Session = Depends(get_db)) -> LeadService:
    """
    Factory function to instantiate the LeadService.
    
    CRITICAL FIX: We pass only the 'db' session. 
    The Service handles initializing its own Repositories internally.
    """
    return LeadService(db)

# --- Endpoints ---

@router.post("/", response_model=LeadOut, status_code=status.HTTP_201_CREATED)
def create_lead(
    lead_in: LeadCreate,
    service: LeadService = Depends(get_service),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new Lead.
    
    - Enforces tenant isolation (Lead belongs to User's Tenant).
    - Sets the current user as the Lead owner.
    """
    if not current_user.tenant_id:
         raise HTTPException(
             status_code=status.HTTP_400_BAD_REQUEST, 
             detail="User is not associated with a valid tenant."
         )
         
    return service.create_lead(
        tenant_id=current_user.tenant_id, 
        owner_id=current_user.id, 
        data=lead_in
    )

@router.get("/", response_model=List[LeadOut])
def list_leads(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    service: LeadService = Depends(get_service),
    current_user: User = Depends(get_current_user)
):
    """
    Get a paginated list of leads for the current tenant.
    """
    if not current_user.tenant_id:
        return []
        
    return service.list_leads(
        tenant_id=current_user.tenant_id, 
        limit=limit, 
        skip=skip
    )

@router.patch("/{lead_id}", response_model=LeadOut)
def update_lead(
    lead_id: int,
    lead_in: LeadUpdate,
    service: LeadService = Depends(get_service),
    current_user: User = Depends(get_current_user)
):
    """
    Update a Lead's details (name, email).
    
    SECURITY: Converted leads cannot be modified.
    
    Returns:
        Updated lead object
        
    Raises:
        400: If lead is converted (immutable)
        404: If lead not found
    """
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no tenant."
        )
    
    try:
        return service.update_lead(
            tenant_id=current_user.tenant_id,
            lead_id=lead_id,
            updates=lead_in.model_dump(exclude_unset=True)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error updating lead {lead_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update lead."
        )

@router.post("/{lead_id}/convert", response_model=DealOut)
def convert_lead_to_deal(
    lead_id: int,
    value_cents: int = Query(..., description="Estimated value of the deal in cents", ge=0),
    service: LeadService = Depends(get_service),
    current_user: User = Depends(get_current_user)
):
    """
    Promote a Lead to a Deal.
    
    - Atomic Operation: Updates Lead status -> Creates Deal -> Fires Event.
    - Idempotent: Will fail if Lead is already converted.
    """
    if not current_user.tenant_id:
         raise HTTPException(
             status_code=status.HTTP_400_BAD_REQUEST, 
             detail="User has no tenant."
         )

    try:
        return service.promote_to_deal(
            tenant_id=current_user.tenant_id,
            lead_id=lead_id,
            value_cents=value_cents,
            seller_id=current_user.id
        )
    except ValueError as e:
        # Catch business rule violations (e.g. "Lead already converted")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        # Catch unexpected server errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Failed to promote lead."
        )