# app/services/chat_service.py
"""
Module: Chat Service
Context: Pod C - Module 3 (Chat/NLP).

Handles the business logic for managing conversations, threading messages,
and integrating NLP analysis.
"""

from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from app.models import Conversation, ChatMessage
from app.nlp.simple_nlp import SimpleNLPService 
import logging

logger = logging.getLogger(__name__)

class ChatService:
    """
    Service for managing chat threads and incoming messages.
    """

    def __init__(self, db: Session, nlp_service: SimpleNLPService | None = None):
        """
        Args:
            db: Database session.
            nlp_service: Optional injection of NLP service for testing/flexibility.
        """
        self.db = db
        self.nlp_service = nlp_service if nlp_service else SimpleNLPService()

    def upsert_conversation(self, customer_number: str, window_minutes=30) -> Conversation:
        """
        Finds an active conversation thread or creates a new one based on a time window.
        
        Args:
            customer_number: The phone number of the customer.
            window_minutes: Time in minutes to consider a conversation 'active'.
        """
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
        Saves a new incoming message, updates the thread timestamp, and runs the NLP pipeline.

        Args:
            from_number: Sender's phone number.
            text: The message content.
            message_id: The WhatsApp Message ID (wamid) for tracking status (Module 6).
        """
        convo = self.upsert_conversation(from_number)
        
        # Run NLP pipeline
        nlp_data = self.nlp_service.analyze_text(text) 

        # Create the message record
        msg = ChatMessage(
            conversation_id=convo.id,
            from_number=from_number,
            text=text,
            message_id=message_id, # Capture the ID here
            language=nlp_data["language"],
            intent=nlp_data["intent"], 
            created_at=datetime.now(timezone.utc)
        )
        self.db.add(msg)
        
        # Update the conversation's "last active" time
        convo.last_message_at = datetime.now(timezone.utc)
        
        self.db.commit()
        self.db.refresh(msg)
        return msg
    
    def list_conversation(self, convo_id: int, limit=50):
        """Retrieves recent messages for a specific conversation."""
        return self.db.query(ChatMessage)\
            .filter(ChatMessage.conversation_id==convo_id)\
            .order_by(ChatMessage.created_at.desc())\
            .limit(limit).all()