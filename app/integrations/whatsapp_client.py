# app/integrations/whatsapp_client.py
"""
Module: WhatsApp Client
Context: Pod C - Integrations

Unified client for interacting with the WhatsApp Cloud API.
Provides both Synchronous (for Celery) and Asynchronous (for FastAPI) methods.
Includes automatic retries for network resilience.
"""

import logging
import httpx
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.core.config import settings

logger = logging.getLogger(__name__)

class WhatsAppClient:
    """
    Wrapper for WhatsApp Cloud API.
    """
    def __init__(self):
        if not settings.WHATSAPP_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
            logger.critical("WhatsApp credentials missing. Messages will fail.")
            
        self.base_url = f"https://graph.facebook.com/v17.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
        self.headers = {
            "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        }

    def _build_payload(self, to_number: str, template_name: str, language: str, components: list):
        """Helper to construct the JSON payload."""
        template_components = []
        if components:
            template_components = [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": str(c)} for c in components]
                }
            ]

        return {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language},
                "components": template_components
            }
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(requests.exceptions.RequestException)
    )
    def send_template_sync(self, to_number: str, template_name: str, language: str = "en_US", components: list = None):
        """
        Synchronous Send - Optimized for Celery Workers.
        """
        payload = self._build_payload(to_number, template_name, language, components)
        try:
            response = requests.post(self.base_url, headers=self.headers, json=payload, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"WhatsApp Sync Send Failed to {to_number}: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError)
    )
    async def send_template_async(self, to_number: str, template_name: str, language: str = "en_US", components: list = None):
        """
        Asynchronous Send - Optimized for FastAPI Endpoints.
        """
        payload = self._build_payload(to_number, template_name, language, components)
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.base_url, headers=self.headers, json=payload, timeout=10)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"WhatsApp Async Send Failed to {to_number}: {e}")
                raise

# Global instance for ease of import
whatsapp_client = WhatsAppClient()