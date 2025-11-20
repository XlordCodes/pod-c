# --- app/services/summary_service.py ---
import os
import requests
import logging
from sqlalchemy.orm import Session
from app.services.chat_service import ChatService

logger = logging.getLogger(__name__)

COHERE_API_KEY = os.getenv("COHERE_API_KEY")
CHAT_URL = "https://api.cohere.ai/v1/chat"

class SummaryService:
    def __init__(self, db: Session):
        self.db = db

    def summarize_conversation(self, convo_id: int):
        """Summarize a conversation's recent history using Cohere."""
        chat_svc = ChatService(self.db)
        messages = chat_svc.list_conversation(convo_id, limit=20)
        
        if not messages:
            return "No messages to summarize."

        # Format history
        history_text = "\n".join([f"{m.from_number}: {m.text}" for m in reversed(messages)])
        
        # Cohere Prompt
        prompt = f"Summarize the following WhatsApp conversation in less than 100 words:\n\n{history_text}"

        payload = {
            "model": "command-r-08-2024", # High performance model
            "message": prompt,
            "temperature": 0.3,
            "max_tokens": 150
        }
        headers = {
            "Authorization": f"Bearer {COHERE_API_KEY}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(CHAT_URL, json=payload, headers=headers, timeout=20)
            response.raise_for_status()
            return response.json()["text"]
        except Exception as e:
            logger.error(f"Error generating summary with Cohere: {e}")
            return "Error generating summary."