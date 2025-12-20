from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict

from app.database import get_db
from app.models import Contact, User
from app.authentication.router import get_current_user 

router = APIRouter()

# --- SECURE Pydantic Models ---
class ContactIn(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    # REMOVED: owner_id. The user cannot choose the owner; the system assigns it.

class ContactOut(BaseModel):
    id: int
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    owner_id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# --- SECURE ENDPOINTS ---

@router.post("/contacts", response_model=ContactOut)
def create_contact(
    contact: ContactIn, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Creates a new contact owned by the currently logged-in user.
    """
    # We unpack the input data (**contact.dict()) AND forcibly set the owner_id
    db_contact = Contact(**contact.dict(), owner_id=current_user.id)
    
    try:
        db.add(db_contact)
        db.commit()
        db.refresh(db_contact)
        return db_contact
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Could not create contact. Email might be duplicate.")

@router.get("/contacts", response_model=List[ContactOut])
def get_contacts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all contacts belonging to the CURRENT user only.
    """
    return db.query(Contact).filter(Contact.owner_id == current_user.id).order_by(Contact.created_at.desc()).all()

@router.get("/contacts/{contact_id}", response_model=ContactOut)
def get_contact(
    contact_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific contact, BUT only if it belongs to the current user.
    """
    contact = db.query(Contact).filter(
        Contact.id == contact_id, 
        Contact.owner_id == current_user.id # Security Check
    ).first()
    
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact

@router.delete("/contacts/{contact_id}")
def delete_contact(
    contact_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a contact, BUT only if it belongs to the current user.
    """
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.owner_id == current_user.id # Security Check
    ).first()
    
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    db.delete(contact)
    db.commit()
    return {"status": "deleted"}