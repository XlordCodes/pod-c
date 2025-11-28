# --- app/services/reply_service.py ---
import os
import requests
import logging
from sqlalchemy.orm import Session
from app.models import ChatMessage
from app.models_reply import ReplySuggestion

logger = logging.getLogger(__name__)

COHERE_API_KEY = os.getenv("COHERE_API_KEY")
CHAT_URL = "https://api.cohere.ai/v1/chat"

class ReplyService:
    def __init__(self, db: Session):
        self.db = db

    def suggest_replies(self, conversation_id: int, top_k=3):
        """Generates suggested replies using Cohere."""
        if not COHERE_API_KEY:
            raise ValueError("COHERE_API_KEY not configured.")

        # 1. Fetch Context
        msgs = (
            self.db.query(ChatMessage)
            .filter(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(5)
            .all()
        )
        
        if not msgs:
            return []

        history = "\n".join(f"{m.from_number}: {m.text}" for m in reversed(msgs))
        
        # 2. Prompt
        prompt = (
            f"Given this chat history, suggest {top_k} concise, professional, and helpful replies "
            f"for the agent to send next. Format as a simple list (no numbering).\n\nContext:\n{history}"
        )

        payload = {
            "model": "command-r-08-2024",
            "message": prompt,
            "temperature": 0.7, 
            "max_tokens": 200
        }
        headers = {
            "Authorization": f"Bearer {COHERE_API_KEY}",
            "Content-Type": "application/json"
        }

        # 3. Call Cohere
        try:
            r = requests.post(CHAT_URL, json=payload, headers=headers, timeout=15)
            r.raise_for_status()
            content = r.json()["text"]
        except Exception as e:
            logger.error(f"Reply generation failed: {e}")
            return []

        # 4. Parse and Store
        lines = [line.strip().lstrip("- ").lstrip("123. ") for line in content.split("\n") if line.strip()]
        
        suggestions_objects = []
        last_msg_id = msgs[0].id 
        
        for i, text in enumerate(lines[:top_k]):
            suggestion = ReplySuggestion(
                message_id=last_msg_id,
                suggestion=text,
                rank=i+1
            )
            self.db.add(suggestion)
            suggestions_objects.append(suggestion)
            
        self.db.commit()
        return suggestions_objects