# app/api/vector.py
"""
Module: Vector & Summarization API
Context: Pod C - Module 4 (AI).

Exposes endpoints to:
1. Manually trigger embedding for a message.
2. Search for similar messages (Semantic Search).
3. Summarize conversation history.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.embedding_service import EmbeddingService
from app.services.summary_service import SummaryService
from app.models import ChatMessage

router = APIRouter()

@router.post("/embed-message")
def embed_message(message_id: int, db: Session = Depends(get_db)):
    """
    Trigger embedding generation for a specific message.
    Useful for backfilling or re-indexing specific rows.
    """
    msg = db.get(ChatMessage, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
        
    svc = EmbeddingService(db)
    try:
        vector = svc.embed_text(msg.text)
        svc.store_embedding(message_id, vector)
        return {"status": "embedded", "message_id": message_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/similar")
def find_similar(text: str, db: Session = Depends(get_db)):
    """
    Find messages semantically similar to the input text.
    Returns a list of matches with distance scores.
    """
    svc = EmbeddingService(db)
    try:
        vector = svc.embed_text(text)
        results = svc.search_similar(vector)
        return [{"message_id": r[0], "distance": r[1]} for r in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/summarize/{cid}")
def summarize_conversation(cid: int, db: Session = Depends(get_db)):
    """
    Generate an AI summary for the given conversation ID.
    Uses the ChatService to fetch history and Cohere to summarize.
    """
    svc = SummaryService(db)
    summary = svc.summarize_conversation(cid)
    return {"conversation_id": cid, "summary": summary}