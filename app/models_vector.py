# app/models_vector.py
from sqlalchemy import Column, Integer, DateTime, ForeignKey
from pgvector.sqlalchemy import VECTOR
from datetime import datetime, timezone
from app.models import Base

class MessageEmbedding(Base):
    """
    Stores vector embeddings for ChatMessages to enable semantic search.
    Requires the 'pgvector' extension in PostgreSQL.
    """
    __tablename__ = "message_embeddings"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("chat_messages.id"), nullable=False)
    
    # 1024 dimensions match the Cohere embed-english-v3.0 model
    vector = Column(VECTOR(1024)) 
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))