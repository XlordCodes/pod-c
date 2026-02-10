# app/api/contacts.py
"""
Module: Contacts API Router
Context: Pod A - Interface Layer.

Exposes REST endpoints for managing Contacts.
Delegates all business logic, validation, and caching to ContactService.
"""

from typing import List
from fastapi import APIRouter, HTTPException, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.auth import User
from app.authentication.router import get_current_user 
from app.services.contact_service import ContactService
from app.schemas.crm import ContactCreate, ContactUpdate, ContactOut

router = APIRouter()

# --- Dependency Injection ---

def get_service(db: Session = Depends(get_db)) -> ContactService:
    """
    Factory to create the ContactService with the current DB session.
    """
    return ContactService(db)

# --- Endpoints ---

@router.post("/contacts", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
async def create_contact(
    contact: ContactCreate, 
    current_user: User = Depends(get_current_user),
    service: ContactService = Depends(get_service)
):
    """
    Create a new contact.
    
    - Enforces tenant isolation.
    - Invalidates the user's contact list cache.
    """
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="User must belong to a tenant to create contacts."
        )

    try:
        return await service.create_contact(
            tenant_id=current_user.tenant_id,
            owner_id=current_user.id,
            data=contact
        )
    except ValueError as e:
        # Catch duplicate email/phone errors from service
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal Server Error")

@router.get("/contacts", response_model=List[ContactOut])
async def get_contacts(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    service: ContactService = Depends(get_service)
):
    """
    Get all contacts for the current user.
    
    - Uses Read-Through Caching (Redis).
    """
    return await service.list_contacts(
        owner_id=current_user.id, 
        skip=skip, 
        limit=limit
    )

@router.get("/contacts/{contact_id}", response_model=ContactOut)
async def get_contact(
    contact_id: int, 
    current_user: User = Depends(get_current_user),
    service: ContactService = Depends(get_service)
):
    """
    Get a specific contact by ID.
    """
    try:
        return await service.get_contact(contact_id, current_user.id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")

@router.put("/contacts/{contact_id}", response_model=ContactOut)
async def update_contact(
    contact_id: int,
    contact_update: ContactUpdate,
    current_user: User = Depends(get_current_user),
    service: ContactService = Depends(get_service)
):
    """
    Update a contact.
    
    - Clears the cache for this user.
    """
    try:
        return await service.update_contact(contact_id, current_user.id, contact_update)
    except ValueError as e:
        # Check if error message implies 'Not Found' or 'Conflict'
        if "not found" in str(e).lower():
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/contacts/{contact_id}")
async def delete_contact(
    contact_id: int, 
    current_user: User = Depends(get_current_user),
    service: ContactService = Depends(get_service)
):
    """
    Delete a contact.
    """
    try:
        await service.delete_contact(contact_id, current_user.id)
        return {"status": "deleted"}
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")