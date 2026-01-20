# app/api/replies.py
"""
Module: AI Reply Suggestions API
Context: Pod C - Module 5 (AI).

Exposes endpoints to:
1. Force sentiment analysis on a message.
2. Generate RAG-based reply suggestions for agents.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.sentiment_service import SentimentService
from app.services.reply_service import ReplyService
from app.models import ChatMessage

router = APIRouter()

@router.post("/sentiment/{message_id}")
def tag_sentiment(message_id: int, db: Session = Depends(get_db)):
    """
    Manually trigger sentiment analysis for a message.
    Updates the 'sentiment' column in the chat_messages table.
    """
    # Verify message exists first
    msg = db.get(ChatMessage, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    svc = SentimentService(db)
    result = svc.analyze_and_store(message_id)
    return {"message_id": message_id, "sentiment": result}

@router.post("/replies/{convo_id}")
def suggest_replies(convo_id: int, db: Session = Depends(get_db)):
    """
    Generate 3 AI-suggested replies based on conversation history 
    and similar past resolved cases (RAG).
    """
    svc = ReplyService(db)
    suggestions = svc.suggest_replies(convo_id)
    return [
        {"id": s.id, "suggestion": s.suggestion, "rank": s.rank} 
        for s in suggestions
    ]