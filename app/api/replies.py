# app/api/replies.py
"""
Module: AI Reply Suggestions API
Context: Pod C - Module 5 (AI).

Exposes endpoints to:
1. Force sentiment analysis on a specific message.
2. Generate RAG-based reply suggestions for agents using the ReplyService.
"""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.sentiment_service import SentimentService
from app.services.reply_service import ReplyService
from app.models import ChatMessage

router = APIRouter()

@router.post("/sentiment/{message_id}")
def tag_sentiment(message_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Manually trigger sentiment analysis for a message.
    
    This endpoint utilizes the local SentimentService (Transformer-based) to 
    analyze the text content of a message and update its 'sentiment' column 
    (e.g., 'positive', 'negative', 'neutral').

    Args:
        message_id (int): The primary key of the chat message to analyze.
        db (Session): Database session dependency.

    Returns:
        dict: A dictionary containing the message_id and the detected sentiment label.

    Raises:
        HTTPException 404: If the message_id does not exist in the database.
    """
    # Verify message existence before initializing heavy services
    msg = db.get(ChatMessage, message_id)
    if not msg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Message not found"
        )

    # Initialize the service which may lazy-load the model
    svc = SentimentService(db)
    result = svc.analyze_and_store(message_id)
    
    return {"message_id": message_id, "sentiment": result}

@router.post("/replies/{convo_id}")
def suggest_replies(convo_id: int, db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """
    Generate AI-suggested replies based on conversation history and similar past cases.

    This uses the ReplyService, which performs a RAG (Retrieval Augmented Generation) 
    pipeline:
    1. Fetches recent conversation history.
    2. Searches the Vector DB for semantically similar past resolved messages.
    3. Uses OpenAI GPT to synthesize 3 context-aware reply options.

    Args:
        convo_id (int): The ID of the active conversation.
        db (Session): Database session dependency.

    Returns:
        List[Dict]: A list of suggestion objects, each containing:
            - id: The database ID of the suggestion.
            - suggestion: The text content of the reply.
            - rank: The priority rank (1-3).
    
    Raises:
        HTTPException 500: If the AI service fails or configuration is missing.
    """
    svc = ReplyService(db)
    
    try:
        suggestions = svc.suggest_replies(convo_id)
        
        # Serialize the SQLAlchemy objects to a JSON-compatible list
        return [
            {
                "id": s.id, 
                "suggestion": s.suggestion, 
                "rank": s.rank
            } 
            for s in suggestions
        ]
        
    except Exception as e:
        # Catch-all for AI provider errors, network timeouts, or DB locking issues
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate replies: {str(e)}"
        )