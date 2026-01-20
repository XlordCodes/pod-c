# --- app/api/chat.py ---
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Any

from app.database import get_db 
from app.services.chat_service import ChatService
from app.models import Conversation, ChatMessage, User
# Import the Auth Dependency to lock down the endpoints
from app.authentication.router import get_current_user

router = APIRouter()

@router.get("/conversations")
def list_conversations(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists active conversations ordered by the most recent message.
    
    - **skip**: Number of conversations to skip (for pagination).
    - **limit**: Maximum number of conversations to return (default 50).
    - **Requires**: Authentication.
    """
    conversations = (
        db.query(Conversation)
        .order_by(Conversation.last_message_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return conversations

@router.get("/conversations/{cid}")
def get_messages(
    cid: int, 
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fetches message history for a specific conversation ID.
    
    - **cid**: Conversation ID.
    - **limit**: Number of messages to retrieve (default 50).
    - **Requires**: Authentication.
    """
    # We rely on the Service layer for the logic, keeping the router clean
    return ChatService(db).list_conversation(cid, limit=limit)