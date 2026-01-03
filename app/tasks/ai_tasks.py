# app/tasks/ai_tasks.py
import logging
from app.core.celery_app import celery_app
from app.database import SessionLocal
# FIX: Ensure this import comes from app.models
from app.models import ChatMessage
# Services
from app.services.sentiment_service import SentimentService
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

@celery_app.task(name="process_message_ai")
def process_message_ai(message_id: int):
    """
    Background task to run AI pipelines on a new message.
    1. Sentiment Analysis (HuggingFace)
    2. Vector Embedding (Cohere)
    """
    db = SessionLocal()
    try:
        msg = db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
        if not msg:
            logger.warning(f"AI Task: Message {message_id} not found.")
            return

        # --- 1. Sentiment Analysis ---
        try:
            # Note: SentimentService loads the model. 
            # In the worker process, this is fine (and expected).
            sentiment_svc = SentimentService(db)
            detected_sentiment = sentiment_svc.analyze_and_store(msg.id)
            logger.info(f"AI Task: Msg {msg.id} sentiment -> {detected_sentiment}")
        except Exception as e:
            logger.error(f"AI Task: Sentiment failed for msg {msg.id}: {e}")

        # --- 2. Vector Embedding (RAG) ---
        try:
            if msg.text and len(msg.text.strip()) > 0:
                embed_svc = EmbeddingService(db)
                vector = embed_svc.embed_text(msg.text)
                embed_svc.store_embedding(msg.id, vector)
                logger.info(f"AI Task: Msg {msg.id} embedded successfully.")
        except Exception as e:
            logger.error(f"AI Task: Embedding failed for msg {msg.id}: {e}")

    finally:
        db.close()