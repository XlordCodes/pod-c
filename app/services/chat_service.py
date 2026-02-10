# app/services/chat_service.py
"""
Module: Chat Service
Context: Pod C - Module 3, 4, 5.

The central nervous system that orchestrates:
1. Message Persistence (DB)
2. NLP Tagging (Simple)
3. Dispatching AI Tasks (Celery)
4. Generic Message CRUD (for API Routers)
"""

import logging
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.models import Conversation, ChatMessage
from app.nlp.simple_nlp import SimpleNLPService

# Import task for async processing
from app.tasks.ai_tasks import process_message_ai

logger = logging.getLogger(__name__)

class ChatService:
    def __init__(self, db: Session, nlp_service: SimpleNLPService | None = None):
        self.db = db
        self.nlp_service = nlp_service if nlp_service else SimpleNLPService()

    # --- Conversation Logic ---
    
    def upsert_conversation(self, customer_number: str, window_minutes=30) -> Conversation:
        """
        Finds an active conversation (within window) or creates a new one.
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

    def list_conversation(self, convo_id: int, limit=50) -> List[ChatMessage]:
        """
        List messages for a specific conversation ID.
        """
        return self.db.query(ChatMessage)\
            .filter(ChatMessage.conversation_id == convo_id)\
            .order_by(ChatMessage.created_at.desc())\
            .limit(limit).all()

    # --- Message Ingestion (Webhook / Manual) ---

    def save_incoming(self, from_number: str, text: str, message_id: str = None, message_type: str = "text") -> ChatMessage:
        """
        Saves incoming message and triggers the background AI pipeline.
        This is the primary entry point for Webhooks and API manual creation.
        """
        try:
            convo = self.upsert_conversation(from_number)
            
            # 1. NLP Tagging (Sync - Fast Regex)
            nlp_data = self.nlp_service.analyze_text(text) 

            # 2. Save Message
            msg = ChatMessage(
                conversation_id=convo.id,
                from_number=from_number,
                text=text,
                message_id=message_id,
                message_type=message_type,
                language=nlp_data.get("language", "en"),
                intent=nlp_data.get("intent", "unknown"), 
                sentiment="neutral", # Updated by Celery later
                created_at=datetime.now(timezone.utc)
            )
            
            self.db.add(msg)
            
            # Update conversation timestamp to keep it "Active"
            convo.last_message_at = datetime.now(timezone.utc)
            
            self.db.commit()
            self.db.refresh(msg)
            
            # 3. Trigger Async AI Pipelines via Celery
            # Returns immediately so Webhook/API doesn't hang
            if message_type == "text":
                process_message_ai.delay(msg.id)

            return msg

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to save incoming message from {from_number}: {e}")
            raise e

    # --- Generic Message CRUD (For Messages Router) ---
    
    def get_message(self, message_id: int) -> ChatMessage:
        """Fetch a single message by ID."""
        msg = self.db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
        if not msg:
            raise ValueError("Message not found")
        return msg

    def list_messages(self, from_number: Optional[str] = None, message_type: Optional[str] = None, limit: int = 50) -> List[ChatMessage]:
        """
        Generic filterable list of messages.
        Used by the API to browse message history outside of a conversation context.
        """
        query = self.db.query(ChatMessage)
        
        if from_number:
            query = query.filter(ChatMessage.from_number == from_number)
        
        if message_type:
             query = query.filter(ChatMessage.message_type == message_type)
            
        return query.order_by(ChatMessage.created_at.desc()).limit(limit).all()

    def delete_message(self, message_id: int):
        """Hard delete a message."""
        msg = self.get_message(message_id)
        self.db.delete(msg)
        self.db.commit()