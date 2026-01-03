# app/services/embedding_service.py
import requests
import logging
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models import MessageEmbedding
from app.core.config import settings

logger = logging.getLogger(__name__)

EMBED_URL = "https://api.cohere.ai/v1/embed"

class EmbeddingService:
    def __init__(self, db: Session):
        self.db = db

    def embed_text(self, text: str) -> list[float]:
        if not settings.COHERE_API_KEY:
            logger.error("COHERE_API_KEY is not configured.")
            raise ValueError("COHERE_API_KEY is not configured.")

        payload = {
            "model": "embed-english-v3.0",
            "texts": [text],
            "input_type": "search_document"
        }
        headers = {
            "Authorization": f"Bearer {settings.COHERE_API_KEY}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(EMBED_URL, json=payload, headers=headers, timeout=20)
            response.raise_for_status()
            return response.json()["embeddings"][0]
        except requests.exceptions.RequestException as e:
            logger.error(f"Error embedding text with Cohere: {e}")
            raise

    def store_embedding(self, message_id: int, vector: list[float]):
        """Save the vector to the database."""
        emb = MessageEmbedding(message_id=message_id, embedding=vector)
        self.db.add(emb)
        self.db.commit()
        self.db.refresh(emb)
        return emb

    def search_similar(self, vector: list[float], limit=5):
        """Search for similar messages using Cosine Distance."""
        # FIX: Updated SQL to use 'embedding' column
        sql = text("""
            SELECT message_id, embedding <=> :vec as distance 
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