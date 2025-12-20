# app/services/sentiment_service.py
"""
Module: Sentiment Analysis Service
Context: Pod C - Module 5 (AI Sentiment).

This service uses a local Transformer model (Hugging Face) to tag incoming
messages with sentiment labels (positive, negative, neutral).
"""

import logging
from sqlalchemy.orm import Session
from app.models import ChatMessage
# transformers is a heavy import; it loads the model into memory.
from transformers import pipeline

logger = logging.getLogger(__name__)

# Initialize the pipeline at module level.
# This ensures the model is loaded once (singleton pattern) rather than per-request.
# It downloads the default model (~200MB) to HF_HOME on first run.
try:
    sentiment_pipeline = pipeline("sentiment-analysis")
except Exception as e:
    logger.error(f"Failed to load sentiment model: {e}")
    sentiment_pipeline = None

class SentimentService:
    def __init__(self, db: Session):
        self.db = db

    def analyze_and_store(self, message_id: int) -> str:
        """
        Analyzes the sentiment of a stored message and updates its record.
        
        Args:
            message_id (int): The ID of the ChatMessage to analyze.
            
        Returns:
            str: The detected sentiment label (e.g., 'positive', 'negative').
        """
        if not sentiment_pipeline:
            logger.warning("Sentiment pipeline not active. Skipping analysis.")
            return "unknown"

        # Fetch the message object
        message = self.db.get(ChatMessage, message_id)
        if not message:
            raise ValueError(f"Message ID {message_id} not found.")

        # Pre-check: Don't crash on empty text (e.g., image-only messages)
        if not message.text or not message.text.strip():
            return "neutral"

        # Truncate text to 512 tokens (standard BERT limit) to prevent crashes
        text_sample = message.text[:512]
        
        try:
            # Run inference
            result = sentiment_pipeline(text_sample)[0]
            label = result["label"].lower() # Standardize to lowercase
            
            # Persist result
            message.sentiment = label
            self.db.commit()
            self.db.refresh(message)
            
            return label
            
        except Exception as e:
            logger.error(f"Sentiment analysis inference failed: {e}")
            return "error"