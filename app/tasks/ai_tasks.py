# app/tasks/ai_tasks.py
"""
Module: AI Background Tasks
Context: Pod C - Async Intelligence

Pipeline:
1. Sentiment Analysis (Local HuggingFace Model)
2. Vector Embedding (OpenAI API)

This task is triggered asynchronously after a new ChatMessage is saved.
"""

import logging
from app.core.celery_app import celery_app
from app.database import SessionLocal
from app.models.chat import ChatMessage
# Services
from app.services.sentiment_service import SentimentService
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

@celery_app.task(name="process_message_ai", bind=True, max_retries=3)
def process_message_ai(self, message_id: int):
    """
    Background task to enrich a message with AI metadata.
    """
    db = SessionLocal()
    try:
        # 1. Fetch Message
        msg = db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
        if not msg:
            logger.warning(f"AI Task: Message {message_id} not found.")
            return

        # Skip empty messages (e.g., image-only)
        if not msg.text or not msg.text.strip():
            logger.info(f"AI Task: Msg {message_id} is empty. Skipping AI.")
            return

        # --- 2. Sentiment Analysis (Local) ---
        try:
            # Note: SentimentService uses Lazy Loading for the model
            sentiment_svc = SentimentService(db)
            detected_sentiment = sentiment_svc.analyze_and_store(msg.id)
            logger.info(f"AI Task: Msg {msg.id} sentiment -> {detected_sentiment}")
        except Exception as e:
            logger.error(f"AI Task: Sentiment failed for msg {msg.id}: {e}")
            # We do NOT retry strictly for local model failures as they are usually deterministic

        # --- 3. Vector Embedding (OpenAI) ---
        try:
            embed_svc = EmbeddingService(db)
            
            # Generate Vector (1536 dims for text-embedding-3-small)
            vector = embed_svc.embed_text(msg.text)
            
            # Store in pgvector column
            embed_svc.store_embedding(msg.id, vector)
            logger.info(f"AI Task: Msg {msg.id} embedded successfully.")
            
        except Exception as e:
            logger.error(f"AI Task: Embedding failed for msg {msg.id}: {e}")
            # Retry on network/API errors
            raise self.retry(exc=e, countdown=10)

    except Exception as e:
        logger.error(f"AI Task: Critical Failure on msg {message_id}: {e}")
    finally:
        db.close()