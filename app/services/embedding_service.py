# --- app/services/embedding_service.py ---
import os
import requests
import logging
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models_vector import MessageEmbedding

logger = logging.getLogger(__name__)

COHERE_API_KEY = os.getenv("COHERE_API_KEY")
# Cohere Embed Endpoint
EMBED_URL = "https://api.cohere.ai/v1/embed"

class EmbeddingService:
    def __init__(self, db: Session):
        self.db = db

    def embed_text(self, text: str) -> list[float]:
        """Call Cohere to get the vector embedding for a text string."""
        if not COHERE_API_KEY:
            logger.error("COHERE_API_KEY is not set.")
            raise ValueError("COHERE_API_KEY is not set.")

        # Cohere payload format
        payload = {
            "model": "embed-english-v3.0", # Industry standard for English
            "texts": [text], # Cohere expects a list of strings
            "input_type": "search_document" # Optimized for storage
        }
        headers = {
            "Authorization": f"Bearer {COHERE_API_KEY}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(EMBED_URL, json=payload, headers=headers, timeout=20)
            response.raise_for_status()
            # Cohere returns a list of embeddings, we take the first one
            return response.json()["embeddings"][0]
        except requests.exceptions.RequestException as e:
            logger.error(f"Error embedding text with Cohere: {e}")
            raise

    def store_embedding(self, message_id: int, vector: list[float]):
        """Save the vector to the database."""
        emb = MessageEmbedding(message_id=message_id, vector=vector)
        self.db.add(emb)
        self.db.commit()
        self.db.refresh(emb)
        return emb

    def search_similar(self, vector: list[float], limit=5):
        """Search for similar messages using Cosine Distance."""
        # Note: For Cohere v3 models, Cosine Similarity is recommended.
        # In pgvector, the <=> operator represents Cosine Distance.
        sql = text("""
            SELECT message_id, vector <=> :vec as distance 
            FROM message_embeddings
            ORDER BY distance ASC
            LIMIT :limit
        """)
        
        try:
            rows = self.db.execute(sql, {"vec": str(vector), "limit": limit}).fetchall()
            return rows
        except Exception as e:
            logger.error(f"Error executing similarity search: {e}")
            raise