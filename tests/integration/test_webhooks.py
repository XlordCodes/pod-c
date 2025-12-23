# tests/integration/test_webhooks.py
import pytest
import hmac
import hashlib
import json
from httpx import AsyncClient
from app.core.config import settings


pytestmark = pytest.mark.asyncio

def sign_bytes(content: bytes):
    """Sign the raw bytes using the REAL app secret"""
    if not settings.WHATSAPP_APP_SECRET:
        raise ValueError("WHATSAPP_APP_SECRET is missing in settings/env")
        
    # Use the actual secret from config, not a dummy string
    secret = settings.WHATSAPP_APP_SECRET.encode()
    mac = hmac.new(secret, content, hashlib.sha256)
    return f"sha256={mac.hexdigest()}"

async def test_webhook_lifecycle(client: AsyncClient):
    # 1. Prepare Payload
    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "919999999999",
                        "id": "wamid.TEST",
                        "type": "text",
                        "text": {"body": "Hello Integration"}
                    }]
                }
            }]
        }]
    }

    # 2. Serialize manually to ensure Consistency
    payload_bytes = json.dumps(payload).encode("utf-8")
    
    headers = {
        "X-Hub-Signature": sign_bytes(payload_bytes),
        "Content-Type": "application/json"
    }
    
    # 3. Send raw content
    res = await client.post("/api/webhooks/whatsapp", content=payload_bytes, headers=headers)
    
    # 4. Assert
    assert res.status_code == 200