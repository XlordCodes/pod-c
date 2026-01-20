# app/api/leads.py
"""
Module: Leads API Router
Context: Pod B - Interface Layer (Module 1).

Exposes REST endpoints for managing Leads and promoting them to Deals.
Handles HTTP request validation, authentication context, and service invocation.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

# Core Imports
from app.database import get_db
from app.authentication.router import get_current_user
from app.models.auth import User

# Domain Imports (Pod B Module 1)
from app.repos.lead_repo import LeadRepo
from app.repos.deal_repo import DealRepo
from app.services.lead_service import LeadService
from app.schemas.crm import LeadCreate, LeadOut, PromoteRequest, DealOut

# Initialize Router
router = APIRouter()

# --- Dependency Injection ---

def get_service(db: Session = Depends(get_db)) -> LeadService:
    """
    Factory function to instantiate the LeadService with its required Repositories.
    This pattern allows the Service to remain independent of the specific DB session lifecycle.
    """
    return LeadService(LeadRepo, DealRepo, db)

# --- Endpoints ---

@router.post("/", response_model=LeadOut, status_code=status.HTTP_201_CREATED)
def create_lead(
    payload: LeadCreate, 
    service: LeadService = Depends(get_service),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new Lead in the system.
    
    Args:
        payload: Pydantic schema containing name and email.
        service: Injected LeadService.
        current_user: The authenticated user making the request.
    """
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Tenant context required for this operation."
        )
        
    return service.create_lead(
        tenant_id=current_user.tenant_id, 
        owner_id=current_user.id, 
        data=payload
    )

@router.get("/", response_model=List[LeadOut])
def list_leads(
    skip: int = 0,
    limit: int = 100,
    service: LeadService = Depends(get_service),
    current_user: User = Depends(get_current_user)
):
    """
    Get a paginated list of leads for the current tenant.
    
    Args:
        skip: Records to skip (default 0).
        limit: Max records to return (default 100).
    """
    if not current_user.tenant_id:
        return []
        
    return service.list_leads(current_user.tenant_id, limit, skip)

@router.post("/{lead_id}/promote", response_model=DealOut)
def promote_lead(
    lead_id: int, 
    payload: PromoteRequest, 
    service: LeadService = Depends(get_service),
    current_user: User = Depends(get_current_user)
):
    """
    Promote a Lead to a Deal.
    
    Triggers the 'promote_to_deal' workflow in the service layer.
    If successful, returns the created Deal object.
    
    Args:
        lead_id: The ID of the lead to convert.
        payload: Request body containing 'value_cents'.
    """
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Tenant context required for this operation."
        )

    # Determine seller: use payload ID if provided, else default to current user
    seller_id = payload.seller_id if payload.seller_id else current_user.id

    try:
        deal = service.promote_to_deal(
            tenant_id=current_user.tenant_id,
            lead_id=lead_id,
            value_cents=payload.value_cents,
            seller_id=seller_id
        )
        return deal
    
    except ValueError as e:
        # Map domain-level validation errors (e.g. "already converted") to HTTP 400
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=str(e)
        )
    except Exception as e:
        # Catch unexpected server errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the promotion."
        )