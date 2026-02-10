# app/api/messages.py
"""
Module: Messages API Router
Context: Pod C - Interface Layer.

Exposes REST endpoints for browsing message history and manually sending/logging messages.
Delegates all business logic to ChatService to ensure AI processing (NLP/Embeddings) occurs.
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict, Field

from app.database import get_db
from app.models.auth import User
from app.authentication.router import get_current_user
from app.services.chat_service import ChatService

router = APIRouter()

# --- Pydantic Schemas ---

class MessageIn(BaseModel):
    """
    Payload for creating a new message manually via API.
    """
    from_number: str = Field(..., description="The sender's phone number (E.164 format)")
    text: str = Field(..., description="The content of the message")
    message_type: str = Field(default="text", description="Type of message: text, image, etc.")
    
    # Note: We do not accept 'contact_id' directly anymore. 
    # The system automatically links messages to a Conversation based on 'from_number'.

class MessageOut(BaseModel):
    """
    Response model for a message.
    Maps to the 'ChatMessage' AI-native model.
    """
    id: int
    from_number: Optional[str] = None
    text: Optional[str] = None
    message_type: str = "text"
    
    # AI Metadata (Optional display)
    intent: Optional[str] = "unclassified"
    sentiment: Optional[str] = "neutral"
    
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# --- Dependency Injection ---

def get_service(db: Session = Depends(get_db)) -> ChatService:
    """
    Factory to create the ChatService with the current DB session.
    """
    return ChatService(db)

# --- Endpoints ---

@router.get("/messages", response_model=List[MessageOut])
def get_messages(
    from_number: Optional[str] = Query(None, description="Filter by sender number"),
    message_type: Optional[str] = Query(None, description="Filter by message type (e.g., text, image)"),
    limit: int = Query(50, ge=1, le=500),
    service: ChatService = Depends(get_service),
    current_user: User = Depends(get_current_user)
):
    """
    Fetch message history with optional filters.
    
    - Returns: List of AI-ready 'ChatMessage' objects.
    """
    return service.list_messages(
        from_number=from_number, 
        message_type=message_type, 
        limit=limit
    )

@router.get("/messages/{message_id}", response_model=MessageOut)
def get_message(
    message_id: int, 
    service: ChatService = Depends(get_service),
    current_user: User = Depends(get_current_user)
):
    """
    Get a single message by ID.
    """
    try:
        return service.get_message(message_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Message not found")

@router.post("/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def create_message(
    message: MessageIn, 
    service: ChatService = Depends(get_service),
    current_user: User = Depends(get_current_user)
):
    """
    Manually inject a message into the system.
    
    **CRITICAL:** This uses `save_incoming()`, which ensures:
    1. A Conversation is created/found.
    2. NLP analysis runs (Intent/Sentiment).
    3. Background Celery tasks are triggered (AI Embedding).
    """
    try:
        return service.save_incoming(
            from_number=message.from_number,
            text=message.text,
            message_type=message.message_type
        )
    except Exception as e:
        # Log the specific error in production logs
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to process message: {str(e)}"
        )

@router.delete("/messages/{message_id}")
def delete_message(
    message_id: int, 
    service: ChatService = Depends(get_service),
    current_user: User = Depends(get_current_user)
):
    """
    Hard delete a message.
    """
    try:
        service.delete_message(message_id)
        return {"status": "deleted"}
    except ValueError:
        raise HTTPException(status_code=404, detail="Message not found")