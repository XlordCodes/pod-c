# app/services/chat_service.py
"""
Module: Chat Service
Context: Pod C - Module 3, 4, 5.

The central nervous system that orchestrates:
1. Message Persistence (DB)
2. NLP Tagging (Simple)
3. Sentiment Analysis (AI)
4. Vector Embedding (Search)
"""

from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from app.models import Conversation, ChatMessage
from app.nlp.simple_nlp import SimpleNLPService
from app.services.sentiment_service import SentimentService
# ### NEW: Import Embedding Service ###
from app.services.embedding_service import EmbeddingService
import logging

logger = logging.getLogger(__name__)

class ChatService:
    def __init__(self, db: Session, nlp_service: SimpleNLPService | None = None):
        self.db = db
        self.nlp_service = nlp_service if nlp_service else SimpleNLPService()

    def upsert_conversation(self, customer_number: str, window_minutes=30) -> Conversation:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=window_minutes)
        
        convo = self.db.query(Conversation)\
            .filter(Conversation.customer_number==customer_number,
                    Conversation.last_message_at > cutoff).first()

        if not convo:
            logger.info(f"Creating new conversation for {customer_number}.")
            convo = Conversation(customer_number=customer_number)
            self.db.add(convo)
            self.db.commit()
            self.db.refresh(convo)
        
        return convo

    def save_incoming(self, from_number: str, text: str, message_id: str = None) -> ChatMessage:
        """
        Saves incoming message and runs ALL AI pipelines (NLP, Sentiment, Embedding).
        """
        convo = self.upsert_conversation(from_number)
        
        # 1. NLP Tagging
        nlp_data = self.nlp_service.analyze_text(text) 

        # 2. Save to DB
        msg = ChatMessage(
            conversation_id=convo.id,
            from_number=from_number,
            text=text,
            message_id=message_id,
            language=nlp_data["language"],
            intent=nlp_data["intent"], 
            sentiment="neutral", # Default
            created_at=datetime.now(timezone.utc)
        )
        self.db.add(msg)
        convo.last_message_at = datetime.now(timezone.utc)
        
        self.db.commit()
        self.db.refresh(msg)
        
        # 3. Run AI Pipelines (Non-blocking usually, but direct here for simplicity)
        try:
            # A. Sentiment
            sentiment_svc = SentimentService(self.db)
            detected_sentiment = sentiment_svc.analyze_and_store(msg.id)
            msg.sentiment = detected_sentiment

            # B. Vector Embedding (Module 4)
            # We only embed if there is text content
            if text and len(text.strip()) > 0:
                embed_svc = EmbeddingService(self.db)
                vector = embed_svc.embed_text(text)
                embed_svc.store_embedding(msg.id, vector)
                logger.info(f"Generated embedding for msg {msg.id}")

        except Exception as e:
            logger.error(f"AI Pipeline failed for msg {msg.id}: {e}")

        return msg
    
    def list_conversation(self, convo_id: int, limit=50):
        return self.db.query(ChatMessage)\
            .filter(ChatMessage.conversation_id==convo_id)\
            .order_by(ChatMessage.created_at.desc())\
            .limit(limit).all()