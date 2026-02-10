# app/services/reply_service.py
"""
Module: AI Reply Service
Context: Pod C - AI Intelligence

Generates smart reply suggestions using RAG (Retrieval Augmented Generation).
Combines OpenAI GPT with Vector Search for context-aware answers.
"""

import logging
from typing import List
from sqlalchemy.orm import Session
from openai import OpenAI

from app.models import ChatMessage, ReplySuggestion
from app.services.embedding_service import EmbeddingService
from app.core.config import settings

logger = logging.getLogger(__name__)

class ReplyService:
    def __init__(self, db: Session):
        self.db = db
        self.vector_svc = EmbeddingService(db)
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None

    def suggest_replies(self, conversation_id: int, top_k: int = 3) -> List[ReplySuggestion]:
        """
        Generates reply suggestions using OpenAI + Vector Search.
        """
        if not self.client:
            logger.error("OPENAI_API_KEY is missing. Cannot generate replies.")
            return []

        # 1. Fetch Current Context (Last 5 messages)
        msgs = (
            self.db.query(ChatMessage)
            .filter(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(5)
            .all()
        )
        
        if not msgs:
            return []

        # Find latest customer message for the search query
        last_customer_msg = next((m for m in msgs if m.from_number), None)
        
        # Format history (Chronological)
        history_text = "\n".join(f"User: {m.text}" if m.from_number else f"Agent: {m.text}" for m in reversed(msgs))
        
        # 2. RAG Retrieval: Search for similar past resolved cases
        knowledge_context = ""
        if last_customer_msg and last_customer_msg.text:
            try:
                # A. Generate vector (OpenAI)
                query_vec = self.vector_svc.embed_text(last_customer_msg.text)
                
                # B. Search DB
                similar_results = self.vector_svc.search_similar(query_vec, limit=2)
                
                if similar_results:
                    knowledge_context = "Relevant Past Responses:\n"
                    for res in similar_results:
                        msg_id = res[0]
                        past_msg = self.db.get(ChatMessage, msg_id) 
                        if past_msg and past_msg.text:
                            knowledge_context += f"- {past_msg.text}\n"
            except Exception as e:
                logger.warning(f"RAG lookup failed (proceeding without memory): {e}")

        # 3. Call OpenAI
        prompt = (
            f"Context:\n{history_text}\n\n"
            f"{knowledge_context}\n\n"
            f"Task: Suggest {top_k} short, professional, and helpful replies for the agent."
        )

        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a customer support AI. Output strictly a list of replies separated by newlines. No numbering, no quotes."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.4, 
                max_tokens=200
            )
            
            content = response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"AI Generation failed: {e}")
            return []

        # 4. Parse and Save
        lines = [line.strip().lstrip("- ").lstrip("123. ") for line in content.split("\n") if line.strip()]
        
        suggestions_objects = []
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