# app/services/summary_service.py
"""
Module: Conversation Summarization Service
Context: Pod C - Module 4 (AI Summarization).

This service uses an LLM (Cohere) to generate concise summaries of 
customer conversations. It is typically called by the /vector/summarize endpoint
or a background job to update CRM notes.
"""

import requests
import logging
from sqlalchemy.orm import Session
from app.services.chat_service import ChatService
from app.core.config import settings

logger = logging.getLogger(__name__)

# Cohere Chat API Endpoint
CHAT_URL = "https://api.cohere.ai/v1/chat"

class SummaryService:
    def __init__(self, db: Session):
        self.db = db

    def summarize_conversation(self, convo_id: int) -> str:
        """
        Fetches recent messages and generates a summary using Cohere.
        
        Args:
            convo_id (int): The ID of the conversation to summarize.
            
        Returns:
            str: The generated summary or an error message.
        """
        # Fail fast if API key is missing in configuration
        if not settings.COHERE_API_KEY:
            logger.error("COHERE_API_KEY not configured. Cannot summarize.")
            return "Summarization unavailable (Config Error)."

        # Reuse ChatService to fetch the message history logically
        chat_svc = ChatService(self.db)
        # Limit to last 20 messages to fit within context window and reduce noise
        messages = chat_svc.list_conversation(convo_id, limit=20)
        
        if not messages:
            return "No messages to summarize."

        # Format history for the prompt (Oldest -> Newest usually better for reading, 
        # but reversed list is Newest -> Oldest. We reverse it back for the LLM).
        history_text = "\n".join([f"{m.from_number}: {m.text}" for m in reversed(messages)])
        
        # Construct the System Prompt
        prompt = (
            f"Summarize the following WhatsApp conversation in less than 100 words.\n"
            f"Focus on the customer's intent and any action items.\n\n"
            f"{history_text}"
        )

        payload = {
            "model": "command-r-08-2024", # Optimized for retrieval/summary tasks
            "message": prompt,
            "temperature": 0.3, # Low temperature for factual consistency
            "max_tokens": 150
        }
        headers = {
            "Authorization": f"Bearer {settings.COHERE_API_KEY}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(CHAT_URL, json=payload, headers=headers, timeout=20)
            response.raise_for_status()
            
            # Extract text from Cohere response structure
            return response.json().get("text", "No summary generated.")
            
        except Exception as e:
            logger.error(f"Error generating summary with Cohere: {e}")
            return "Error generating summary."