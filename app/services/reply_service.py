# app/services/reply_service.py
import requests
import logging
from typing import List
from sqlalchemy.orm import Session
from app.models import ChatMessage
from app.models_reply import ReplySuggestion
# Import the Vector Service for RAG (Retrieval Augmented Generation)
from app.services.embedding_service import EmbeddingService
from app.core.config import settings

logger = logging.getLogger(__name__)

CHAT_URL = "https://api.cohere.ai/v1/chat"

class ReplyService:
    """
    Service responsible for generating AI-powered reply suggestions.
    It uses RAG (Retrieval Augmented Generation) to combine:
    1. The current conversation context.
    2. Similar past messages from the Vector Database.
    """
    def __init__(self, db: Session):
        self.db = db
        # Initialize Vector Engine for semantic search
        self.vector_svc = EmbeddingService(db)

    def suggest_replies(self, conversation_id: int, top_k: int = 3) -> List[ReplySuggestion]:
        """
        Generates reply suggestions using Cohere LLM + Vector Search.
        
        Args:
            conversation_id: The ID of the active conversation.
            top_k: Number of suggestions to generate (default 3).
            
        Returns:
            A list of ReplySuggestion objects stored in the DB.
        """
        # Fail fast if AI is not configured in settings
        if not settings.COHERE_API_KEY:
            logger.error("COHERE_API_KEY is missing. Cannot generate replies.")
            return []

        # 1. Fetch Current Conversation Context (Last 5 messages)
        msgs = (
            self.db.query(ChatMessage)
            .filter(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(5)
            .all()
        )
        
        # If no messages exist, we can't generate a reply
        if not msgs:
            return []

        # Find the latest message from the customer to use as our "Search Query"
        # We skip messages sent by the bot/agent (where from_number might be None or ours)
        last_customer_msg = next((m for m in msgs if m.from_number), None)
        
        # Format history for the LLM Prompt (Reverse chronological order for readability)
        history_text = "\n".join(f"User: {m.text}" if m.from_number else f"Agent: {m.text}" for m in reversed(msgs))
        
        # 2. RAG Retrieval: Search for similar past resolved cases
        knowledge_context = ""
        if last_customer_msg and last_customer_msg.text:
            try:
                # A. Generate vector embedding for the incoming question
                query_vec = self.vector_svc.embed_text(last_customer_msg.text)
                
                # B. Search vector DB for semantically similar messages
                # Returns list of tuples: (message_id, distance)
                similar_results = self.vector_svc.search_similar(query_vec, limit=2)
                
                if similar_results:
                    knowledge_context = "\nRelevant Past Responses:\n"
                    for res in similar_results:
                        msg_id = res[0] # Extract ID from tuple
                        
                        # Fetch the actual full text from the standard DB
                        past_msg = self.db.get(ChatMessage, msg_id) 
                        
                        # Only include if it's a valid text message
                        if past_msg and past_msg.text:
                            knowledge_context += f"- {past_msg.text}\n"
            except Exception as e:
                # We catch errors here so the main reply generation doesn't crash 
                # just because the "Memory" feature failed.
                logger.warning(f"RAG lookup failed (proceeding without memory): {e}")

        # 3. Construct the System Prompt
        # We use explicit instructions to force the LLM to output clean data.
        prompt = (
            f"You are a professional customer support agent. "
            f"Suggest {top_k} short, helpful, and polite replies to the latest user message.\n"
            f"Use the Context and Relevant Past Responses below to guide your answer.\n\n"
            f"--- Conversation Context ---\n{history_text}\n\n"
            f"--- {knowledge_context} ---\n\n"
            f"Output Format: Provide ONLY a simple list of {top_k} replies. Do not number them. Do not add quotes."
        )

        # 4. Call the AI Model (Cohere)
        payload = {
            "model": "command-r-08-2024", # High-performance model
            "message": prompt,
            "temperature": 0.3, # Low temperature = deterministic, factual answers
            "max_tokens": 300
        }
        headers = {
            "Authorization": f"Bearer {settings.COHERE_API_KEY}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(CHAT_URL, json=payload, headers=headers, timeout=15)
            response.raise_for_status()
            content = response.json().get("text", "")
        except Exception as e:
            logger.error(f"AI API Call failed: {e}")
            return []

        # 5. Parse Response and Persist to DB
        # We split by newline and filter out empty lines to get clean suggestions
        lines = [line.strip().lstrip("- ").lstrip("123. ") for line in content.split("\n") if line.strip()]
        
        suggestions_objects = []
        # Link suggestions to the most recent message in the thread
        current_msg_id = msgs[0].id 
        
        for i, text in enumerate(lines[:top_k]):
            suggestion = ReplySuggestion(
                message_id=current_msg_id,
                suggestion=text,
                rank=i+1
            )
            self.db.add(suggestion)
            suggestions_objects.append(suggestion)
            
        self.db.commit()
        return suggestions_objects