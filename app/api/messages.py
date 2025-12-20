from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict

from app.database import get_db
from app.models import Message, User
from app.authentication.router import get_current_user

router = APIRouter()

# --- Pydantic Models ---
class MessageIn(BaseModel):
    message_type: str
    from_number: str 
    text: str         
    contact_id: Optional[int] = None

class ContactOut(BaseModel):
    id: int
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class MessageOut(BaseModel):
    id: int
    message_type: Optional[str] = None
    from_number: Optional[str] = None 
    to_number: Optional[str] = None
    text: Optional[str] = None        
    created_at: datetime
    contact: Optional[ContactOut] = None
    
    model_config = ConfigDict(from_attributes=True)

# --- Endpoints (SECURED) ---

@router.get("/messages", response_model=List[MessageOut])
def get_messages(
    from_number: Optional[str] = None,
    message_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) # Security Check
):
    """Fetch messages. Requires Auth."""
    query = db.query(Message)
    
    if from_number:
        query = query.filter(Message.from_number == from_number)
    if message_type:
        query = query.filter(Message.message_type == message_type)
        
    return query.order_by(Message.created_at.desc()).all()

@router.get("/messages/{message_id}", response_model=MessageOut)
def get_message(
    message_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) # Security Check
):
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    return message

@router.post("/messages", response_model=MessageOut)
def create_message(
    message: MessageIn, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) # Security Check
):
    db_message = Message(**message.dict())
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message

@router.delete("/messages/{message_id}")
def delete_message(
    message_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) # Security Check
):
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    db.delete(message)
    db.commit()
    return {"status": "deleted"}