# --- app/api/replies.py ---
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.services.sentiment_service import SentimentService
from app.services.reply_service import ReplyService

router = APIRouter(prefix="/ai", tags=["AI/Replies"])

@router.post("/sentiment/{message_id}")
def analyze_sentiment(message_id: int, db: Session = Depends(get_db)):
    """Force sentiment analysis on a specific message."""
    svc = SentimentService(db)
    result = svc.analyze_and_store(message_id)
    return {"message_id": message_id, "sentiment": result}

@router.post("/suggest/{conversation_id}")
def get_suggestions(conversation_id: int, db: Session = Depends(get_db)):
    """Generate reply suggestions for a conversation."""
    svc = ReplyService(db)
    suggestions = svc.suggest_replies(conversation_id)
    return [
        {"id": s.id, "suggestion": s.suggestion, "rank": s.rank} 
        for s in suggestions
    ]