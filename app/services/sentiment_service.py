# app/services/sentiment_service.py
"""
Module: Sentiment Analysis Service
Context: Pod C - Module 5 (AI Sentiment).

Uses a local Transformer model (Hugging Face) to tag incoming messages.
Implements 'Lazy Loading' to prevent high memory usage during app startup.
"""

import logging
from sqlalchemy.orm import Session
from app.models import ChatMessage

# We import pipeline here, but we DON'T initialize it yet.
try:
    from transformers import pipeline
except ImportError:
    pipeline = None

logger = logging.getLogger(__name__)

# Global singleton to hold the model in memory *after* first load
_sentiment_pipeline = None

def get_pipeline():
    """
    Lazy loader for the sentiment model.
    Only loads the 500MB+ model into RAM when actually needed.
    """
    global _sentiment_pipeline
    
    if _sentiment_pipeline is not None:
        return _sentiment_pipeline

    if pipeline is None:
        logger.error("Transformers library not installed.")
        return None

    try:
        logger.info("⏳ Loading Sentiment Model (this may take a moment)...")
        # 'distilbert-base-uncased-finetuned-sst-2-english' is fast and lightweight
        _sentiment_pipeline = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")
        logger.info("✅ Sentiment Model Loaded.")
        return _sentiment_pipeline
    except Exception as e:
        logger.error(f"Failed to load sentiment model: {e}")
        return None

class SentimentService:
    def __init__(self, db: Session):
        self.db = db

    def analyze_and_store(self, message_id: int) -> str:
        """
        Analyzes the sentiment of a stored message and updates its record.
        """
        # 1. Fetch Pipeline (Lazy Load)
        analyzer = get_pipeline()
        
        if not analyzer:
            logger.warning("Sentiment analysis skipped: Model unavailable.")
            return "service_unavailable"

        # 2. Fetch Message
        message = self.db.get(ChatMessage, message_id)
        if not message:
            logger.error(f"Message ID {message_id} not found.")
            return "error"

        # 3. Validation
        if not message.text or not message.text.strip():
            return "neutral"

        # 4. Inference
        try:
            # Truncate to 512 chars (approx) to respect model token limits safely
            text_sample = message.text[:512]
            
            result = analyzer(text_sample)[0]
            label = result["label"].lower() # e.g., 'positive', 'negative'
            
            # 5. Save Result
            message.sentiment = label
            self.db.commit()
            self.db.refresh(message)
            
            return label
            
        except Exception as e:
            logger.error(f"Inference failed for Msg {message_id}: {e}")
            return "error"