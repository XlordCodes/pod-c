# app/nlp/simple_nlp.py
"""
Module: Lightweight NLP Utilities
Context: Pod C - Module 3 (Incoming Message Parsing).

Provides basic language detection and keyword-based intent classification.
Designed as a placeholder that can be replaced by an LLM or ML model later.
"""

from langdetect import detect
import logging

logger = logging.getLogger(__name__)

class SimpleNLPService:
    # Keyword mapping for heuristic intent detection
    KEYWORDS = {
        "buy": "PURCHASE_INTENT",
        "price": "PRICING_QUERY",
        "cost": "PRICING_QUERY",
        "hello": "GREETING",
        "hi": "GREETING",
        "help": "SUPPORT_QUERY",
        "issue": "SUPPORT_QUERY"
    }

    def analyze_text(self, text: str) -> dict[str, str]:
        """
        Analyzes text to determine language and intent.
        
        Args:
            text (str): The incoming message body.
            
        Returns:
            dict: {'language': str, 'intent': str}
        """
        if not text:
            return {"language": "unknown", "intent": "EMPTY"}

        # 1. Language Detection
        try:
            lang = detect(text)
        except Exception:
            # langdetect throws exception on empty/numeric text
            lang = "unknown"

        # 2. Intent Classification (Keyword Heuristic)
        lower_text = text.lower()
        intent = "UNCLASSIFIED"
        
        for k, tag in self.KEYWORDS.items():
            if k in lower_text:
                intent = tag
                break
                
        # 3. Special Case: Short messages
        if len(text.strip()) < 3 and intent == "UNCLASSIFIED":
            intent = "SHORT_MESSAGE"

        return {"language": lang, "intent": intent}