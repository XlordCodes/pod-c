from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db
from models import Contact
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class ContactIn(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None

class ContactOut(ContactIn):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True

@router.post("/contacts", response_model=ContactOut)
def create_contact(contact: ContactIn, db: Session = Depends(get_db)):
    db_contact = Contact(**contact.dict())
    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)
    return db_contact

@router.get("/contacts", response_model=List[ContactOut])
def get_contacts(db: Session = Depends(get_db)):
    return db.query(Contact).order_by(Contact.created_at.desc()).all()

@router.get("/contacts/{contact_id}", response_model=ContactOut)
def get_contact(contact_id: int, db: Session = Depends(get_db)):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact

@router.delete("/contacts/{contact_id}")
def delete_contact(contact_id: int, db: Session = Depends(get_db)):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    db.delete(contact)
    db.commit()
    return {"status": "deleted"}

