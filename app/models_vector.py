# --- app/models_vector.py ---
from sqlalchemy import Column, Integer, DateTime, ForeignKey
from pgvector.sqlalchemy import VECTOR
from datetime import datetime, timezone
from app.models import Base

class MessageEmbedding(Base):
    __tablename__ = "message_embeddings"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("chat_messages.id"), nullable=False)
    
    # COHERE UPDATE: embed-english-v3.0 uses 1024 dimensions (OpenAI was 1536)
    vector = Column(VECTOR(1024)) 
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))