# app/services/chat_service.py
"""
Module: Chat Service
Context: Pod C - Module 3, 4, 5.

The central nervous system that orchestrates:
1. Message Persistence (DB)
2. NLP Tagging (Simple)
3. Dispatching AI Tasks (Celery)
"""

import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.models import Conversation, ChatMessage
from app.nlp.simple_nlp import SimpleNLPService

# NEW: Import task for async processing
from app.tasks.ai_tasks import process_message_ai

logger = logging.getLogger(__name__)

class ChatService:
    def __init__(self, db: Session, nlp_service: SimpleNLPService | None = None):
        self.db = db
        self.nlp_service = nlp_service if nlp_service else SimpleNLPService()

    def upsert_conversation(self, customer_number: str, window_minutes=30) -> Conversation:
        """
        Finds an active conversation or creates a new one.
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=window_minutes)
        
        convo = self.db.query(Conversation)\
            .filter(Conversation.customer_number == customer_number,
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
        Saves incoming message and triggers the background AI pipeline.
        """
        try:
            convo = self.upsert_conversation(from_number)
            
            # 1. NLP Tagging (Keep this sync as it's fast regex)
            nlp_data = self.nlp_service.analyze_text(text) 

            # 2. Save Message
            msg = ChatMessage(
                conversation_id=convo.id,
                from_number=from_number,
                text=text,
                message_id=message_id,
                language=nlp_data.get("language", "en"),
                intent=nlp_data.get("intent", "unknown"), 
                sentiment="neutral", # Will be updated by Celery worker later
                created_at=datetime.now(timezone.utc)
            )
            
            self.db.add(msg)
            
            # Update conversation timestamp
            convo.last_message_at = datetime.now(timezone.utc)
            
            self.db.commit()
            self.db.refresh(msg)
            
            # 3. Trigger Async AI Pipelines via Celery
            # This returns immediately so the Webhook doesn't time out
            process_message_ai.delay(msg.id)

            return msg

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to save incoming message from {from_number}: {e}")
            raise e

    def list_conversation(self, convo_id: int, limit=50):
        return self.db.query(ChatMessage)\
            .filter(ChatMessage.conversation_id == convo_id)\
            .order_by(ChatMessage.created_at.desc())\
            .limit(limit).all()