# app/integrations/whatsappclient.py
import requests
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

def send_template(to_number: str, template_name: str, language: str = "en_US", components: list = None):
    """
    Sends a WhatsApp template message using credentials from settings.
    Used by the Bulk Service worker.
    """
    if not settings.WHATSAPP_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
        logger.error("WhatsApp credentials missing in settings.")
        return {"error": "Missing credentials"}

    url = f"https://graph.facebook.com/v17.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Construct the component payload if parameters exist
    template_components = []
    if components:
        template_components = [
            {
                "type": "body",
                "parameters": [{"type": "text", "text": str(c.get("text", ""))} for c in components]
            }
        ]

    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language},
            "components": template_components
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send WhatsApp message to {to_number}: {e}")
        raise e