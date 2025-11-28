from langdetect import detect
import logging

logger = logging.getLogger(__name__)

class SimpleNLPService:
    """
    Handles lightweight NLP tasks: language detection and simple keyword-based intent.
    Designed to be easily swapped out for a Transformer model or LLM call.
    """

    KEYWORDS = {
        "buy": "PURCHASE_INTENT",
        "price": "PRICING_QUERY",
        "hello": "GREETING",
        "help": "SUPPORT_QUERY"
    }

    def analyze_text(self, text: str) -> dict[str, str]:
        """Performs language detection and keyword analysis."""
        
        # 1. Language Detection (Safely)
        try:
            lang = detect(text)
        except Exception:
            lang = "unknown"
            logger.warning(f"Could not detect language for text: {text[:30]}...")

        lower_text = text.lower()
        intent = "UNCLASSIFIED"
        
        # 2. Keyword Intent Analysis
        for k, tag in self.KEYWORDS.items():
            if k in lower_text:
                intent = tag
                break
                
        # 3. Handle Empty/Short Text
        if len(text.strip()) < 5:
            intent = "SHORT_MESSAGE"

        return {"language": lang, "intent": intent}