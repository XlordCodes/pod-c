# --- app/api/chat.py (From Module 3) ---
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db 
from app.services.chat_service import ChatService
from app.models import Conversation

router = APIRouter(prefix="/chat", tags=["Chat/NLP"])

@router.get("/conversations")
def list_conversations(db: Session = Depends(get_db)):
    """Lists all conversations ordered by last message time."""
    return db.query(Conversation).order_by(Conversation.last_message_at.desc()).all()

@router.get("/conversations/{cid}")
def get_messages(cid: int, db: Session = Depends(get_db)):
    """Fetches all messages for a specific conversation ID."""
    return ChatService(db).list_conversation(cid)