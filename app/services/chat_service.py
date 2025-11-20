# --- app/services/chat_service.py (Corrected) ---
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from app.models import Conversation, ChatMessage
# FIX: Import the class, not a function
from app.nlp.simple_nlp import SimpleNLPService 
import logging

logger = logging.getLogger(__name__)

class ChatService:
    # FIX: Accept nlp_service as an optional dependency
    def __init__(self, db: Session, nlp_service: SimpleNLPService | None = None):
        self.db = db
        # FIX: Initialize the service if not provided
        self.nlp_service = nlp_service if nlp_service else SimpleNLPService()

    def upsert_conversation(self, customer_number: str, window_minutes=30):
        """Finds active conversation or creates a new one based on time window."""
        
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=window_minutes)
        
        convo = self.db.query(Conversation)\
            .filter(Conversation.customer_number==customer_number,
                    Conversation.last_message_at > cutoff).first()

        if not convo:
            logger.info(f"Creating new conversation for {customer_number}.")
            convo = Conversation(customer_number=customer_number)
            self.db.add(convo)
            self.db.commit(); self.db.refresh(convo)
        return convo

    def save_incoming(self, from_number: str, text: str):
        """Saves a new incoming message, updates the thread, and runs the NLP pipeline."""
        
        convo = self.upsert_conversation(from_number)
        
        # FIX: Call the method on the service instance
        nlp_data = self.nlp_service.analyze_text(text) 

        # Normalize message into ChatMessage row
        msg = ChatMessage(conversation_id=convo.id,
                          from_number=from_number,
                          text=text,
                          language=nlp_data["language"],
                          intent=nlp_data["intent"], 
                          created_at=datetime.now(timezone.utc))
        self.db.add(msg)
        
        # Update last message time on the Conversation thread
        convo.last_message_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(msg)
        return msg
    
    def list_conversation(self, convo_id: int, limit=50):
        """Lists messages for a specific conversation ID."""
        return self.db.query(ChatMessage)\
            .filter(ChatMessage.conversation_id==convo_id)\
            .order_by(ChatMessage.created_at.desc())\
            .limit(limit).all()