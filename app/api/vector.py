# app/api/vector.py
"""
Module: Vector & Summarization API
Context: Pod C - Module 4 (AI).

Exposes endpoints to:
1. Manually trigger embedding for a specific message (Backfilling/Re-indexing).
2. Search for similar messages using Semantic Search (pgvector).
3. Summarize conversation history using LLMs.

SECURITY: All endpoints require JWT authentication.
"""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.embedding_service import EmbeddingService
from app.services.summary_service import SummaryService
from app.models import ChatMessage
from app.authentication.router import get_current_user
from app.models.auth import User

router = APIRouter()

@router.post("/embed-message", status_code=status.HTTP_201_CREATED)
def embed_message(
    message_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Trigger embedding generation for a specific message.
    
    This endpoint retrieves the message text, generates a 1536-dimensional vector 
    embedding via the EmbeddingService (OpenAI), and persists it to the database 
    using an atomic transaction.
    
    SECURITY: Requires valid JWT authentication.
    
    Args:
        message_id (int): The ID of the message to embed.
        db (Session): Database session dependency.
        current_user (User): The authenticated user making the request.
        
    Returns:
        dict: Status and processed message ID.
        
    Raises:
        HTTPException 404: If the message does not exist.
        HTTPException 400: If the embedding service rejects the input (e.g. empty text).
        HTTPException 500: If an internal server or AI service error occurs.
    """
    msg = db.get(ChatMessage, message_id)
    if not msg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Message not found"
        )
        
    svc = EmbeddingService(db)
    try:
        # Generate Vector (Blocking I/O with Retries handled by Service)
        vector = svc.embed_text(msg.text)
        
        # Store with explicit commit to ensure data durability immediately
        svc.store_embedding(message_id, vector, commit=True)
        
        return {"status": "embedded", "message_id": message_id}
        
    except ValueError as e:
        # Handle known validation errors (e.g., empty text, invalid API key)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=str(e)
        )
    except Exception as e:
        # Catch unexpected failures to prevent server crash
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"AI Service unavailable: {str(e)}"
        )

@router.get("/similar")
def find_similar(
    text: str, 
    limit: int = 5, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    Find messages semantically similar to the input text.
    
    Uses Cosine Similarity (via pgvector <=> operator) to rank messages by relevance.
    
    SECURITY: Requires valid JWT authentication.
    
    Args:
        text (str): The query text to compare against.
        limit (int): Maximum number of results to return (default: 5).
        db (Session): Database session dependency.
        current_user (User): The authenticated user making the request.
        
    Returns:
        List[Dict]: A list of matched messages with their IDs and distance scores.
        
    Raises:
        HTTPException 500: If the vector search fails.
    """
    svc = EmbeddingService(db)
    try:
        # Convert query text to vector
        vector = svc.embed_text(text)
        
        # Perform similarity search in DB
        results = svc.search_similar(vector, limit=limit)
        
        # Format results (SQLAlchemy returns tuples)
        return [
            {"message_id": r[0], "distance": r[1]} 
            for r in results
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Vector search failed: {str(e)}"
        )

@router.get("/summarize/{cid}")
def summarize_conversation(
    cid: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Generate an AI summary for the given conversation ID.
    
    Uses the ChatService to fetch message history and the SummaryService (OpenAI)
    to generate a concise summary of the interaction.
    
    SECURITY: Requires valid JWT authentication.
    
    Args:
        cid (int): The Conversation ID.
        db (Session): Database session dependency.
        current_user (User): The authenticated user making the request.
        
    Returns:
        dict: The conversation ID and the generated summary text.
    
    Raises:
        HTTPException 500: If the summarization fails.
    """
    try:
        svc = SummaryService(db)
        summary = svc.summarize_conversation(cid)
        return {"conversation_id": cid, "summary": summary}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Summarization failed: {str(e)}"
        )
