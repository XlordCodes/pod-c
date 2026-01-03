# app/api/contacts.py
import re
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict, field_validator

from app.database import get_db
from app.models import Contact, User
from app.authentication.router import get_current_user 
from app.core.cache import get_cache, set_cache, invalidate_cache

router = APIRouter()

# --- Pydantic Models ---

class ContactBase(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    custom_fields: Optional[Dict[str, Any]] = {}

    @field_validator('phone')
    def validate_phone(cls, v):
        if v is None:
            return v
        # Remove spaces, dashes, parentheses
        clean_number = re.sub(r'[\s\-\(\)]', '', v)
        # Regex for E.164
        if not re.match(r'^\+?[1-9]\d{9,14}$', clean_number):
            raise ValueError('Phone number must be in valid E.164 format')
        return clean_number

class ContactIn(ContactBase):
    pass

class ContactUpdate(BaseModel):
    """Partial update model"""
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    custom_fields: Optional[Dict[str, Any]] = None

class ContactOut(ContactBase):
    id: int
    owner_id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# --- ENDPOINTS ---

@router.post("/contacts", response_model=ContactOut)
async def create_contact(
    contact: ContactIn, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Creates a new contact owned by the user."""
    # Note: owner_id is derived from token, not payload (Security Best Practice)
    db_contact = Contact(
        **contact.model_dump(), 
        owner_id=current_user.id
    )
    
    try:
        db.add(db_contact)
        db.commit()
        db.refresh(db_contact)
        
        await invalidate_cache(f"contacts:{current_user.id}:*")
        return db_contact
        
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Contact with this phone or email already exists.")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/contacts", response_model=List[ContactOut])
async def get_contacts(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all contacts belonging to the CURRENT user."""
    cache_key = f"contacts:{current_user.id}:{skip}:{limit}"
    
    if cached := await get_cache(cache_key):
        return cached

    contacts = db.query(Contact)\
        .filter(Contact.owner_id == current_user.id)\
        .order_by(Contact.created_at.desc())\
        .offset(skip)\
        .limit(limit)\
        .all()
    
    # Serialize for cache
    contacts_data = [ContactOut.model_validate(c).model_dump(mode="json") for c in contacts]
    await set_cache(cache_key, contacts_data, expire=60)
    
    return contacts

@router.get("/contacts/{contact_id}", response_model=ContactOut)
async def get_contact(
    contact_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    contact = db.query(Contact).filter(
        Contact.id == contact_id, 
        Contact.owner_id == current_user.id
    ).first()
    
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact

@router.put("/contacts/{contact_id}", response_model=ContactOut)
async def update_contact(
    contact_id: int,
    contact_update: ContactUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Updates an existing contact."""
    db_contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.owner_id == current_user.id
    ).first()

    if not db_contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    # Update only provided fields
    update_data = contact_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_contact, key, value)

    try:
        db.commit()
        db.refresh(db_contact)
        await invalidate_cache(f"contacts:{current_user.id}:*")
        return db_contact
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Update failed. Phone/Email conflict.")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/contacts/{contact_id}")
async def delete_contact(
    contact_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.owner_id == current_user.id
    ).first()
    
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    db.delete(contact)
    db.commit()
    
    await invalidate_cache(f"contacts:{current_user.id}:*")
    
    return {"status": "deleted"}