# --- app/api/vector.py ---
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.embedding_service import EmbeddingService
from app.services.summary_service import SummaryService
from app.models import ChatMessage

router = APIRouter(prefix="/vector", tags=["AI/Vector"])

@router.post("/embed/{message_id}")
def embed_message(message_id: int, db: Session = Depends(get_db)):
    """Trigger embedding generation for a specific message."""
    msg = db.get(ChatMessage, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
        
    svc = EmbeddingService(db)
    vector = svc.embed_text(msg.text)
    svc.store_embedding(message_id, vector)
    return {"status": "embedded", "message_id": message_id}

@router.get("/similar")
def find_similar(text: str, db: Session = Depends(get_db)):
    """Find messages similar to the input text."""
    svc = EmbeddingService(db)
    vector = svc.embed_text(text)
    results = svc.search_similar(vector)
    return [{"message_id": r[0], "distance": r[1]} for r in results]

@router.get("/summarize/{convo_id}")
def summarize_chat(convo_id: int, db: Session = Depends(get_db)):
    """Summarize a conversation."""
    svc = SummaryService(db)
    summary = svc.summarize_conversation(convo_id)
    return {"conversation_id": convo_id, "summary": summary}