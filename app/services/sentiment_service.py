# --- app/services/sentiment_service.py (Industry Standard) ---
import logging
from sqlalchemy.orm import Session
from app.models import ChatMessage
# Import from transformers
from transformers import pipeline

logger = logging.getLogger(__name__)

# Load the pipeline once at module level to avoid reloading it on every request (Performance)
# This downloads a small default model (~200MB) on the first run.
try:
    sentiment_pipeline = pipeline("sentiment-analysis")
except Exception as e:
    logger.error(f"Failed to load sentiment model: {e}")
    sentiment_pipeline = None

class SentimentService:
    def __init__(self, db: Session):
        self.db = db

    def analyze_and_store(self, message_id: int):
        """Analyzes the sentiment of a message and updates the DB."""
        if not sentiment_pipeline:
            logger.warning("Sentiment pipeline not active.")
            return "unknown"

        message = self.db.get(ChatMessage, message_id)
        if not message:
            raise ValueError("Message not found")

        # Truncate text to 512 chars to fit model limits
        text_sample = message.text[:512]
        
        try:
            result = sentiment_pipeline(text_sample)[0]
            label = result["label"].lower() # e.g., 'positive', 'negative'
            
            # Update DB
            message.sentiment = label
            self.db.commit()
            self.db.refresh(message)
            
            return label
        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            return "error"