from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models import Message
from pydantic import BaseModel, ConfigDict
from datetime import datetime

router = APIRouter()

class MessageIn(BaseModel):
    message_type: str
    sender: str
    message_body: str
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
    message_type: str
    sender: str
    message_body: str
    created_at: datetime
    contact: Optional[ContactOut] = None
    model_config = ConfigDict(from_attributes=True)

@router.get("/messages", response_model=List[MessageOut])
def get_messages(
    sender: Optional[str] = None,
    message_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Message)
    if sender:
        query = query.filter(Message.sender == sender)
    if message_type:
        query = query.filter(Message.message_type == message_type)
    return query.order_by(Message.created_at.desc()).all()

@router.get("/messages/{message_id}", response_model=MessageOut)
def get_message(message_id: int, db: Session = Depends(get_db)):
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    return message

@router.post("/messages", response_model=MessageOut)
def create_message(message: MessageIn, db: Session = Depends(get_db)):
    db_message = Message(**message.dict())
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message

@router.delete("/messages/{message_id}")
def delete_message(message_id: int, db: Session = Depends(get_db)):
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    db.delete(message)
    db.commit()
    return {"status": "deleted"}

