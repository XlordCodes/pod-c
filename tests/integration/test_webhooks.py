# tests/integration/test_webhooks.py
import pytest
import hmac
import hashlib
import json
from httpx import AsyncClient
from app.core.config import settings

pytestmark = pytest.mark.asyncio

def sign_bytes(content: bytes, secret: str):
    """Sign the raw bytes using HMAC-SHA256."""
    secret_bytes = secret.encode()
    mac = hmac.new(secret_bytes, content, hashlib.sha256)
    # Note: Your webhooks.py splits on '=', so we must provide 'prefix=hash'
    return f"sha256={mac.hexdigest()}"

async def test_webhook_lifecycle(client: AsyncClient, monkeypatch):
    """
    Test the WhatsApp webhook endpoint with dynamic secret patching.
    """
    # 1. Setup Mock Secret
    # We patch the Settings object so webhooks.py reads this value
    mock_secret = "test_secret_12345"
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", mock_secret)

    # 2. Prepare Payload
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "123456789",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {
                        "display_phone_number": "1234567890",
                        "phone_number_id": "1234567890"
                    },
                    "contacts": [{"profile": {"name": "Test"}, "wa_id": "919999999999"}],
                    "messages": [{
                        "from": "919999999999",
                        "id": "wamid.TEST",
                        "timestamp": "1600000000",
                        "type": "text",
                        "text": {"body": "Hello Integration"}
                    }]
                },
                "field": "messages"
            }]
        }]
    }

    # 3. Serialize
    payload_bytes = json.dumps(payload).encode("utf-8")
    
    # 4. Generate Signature
    signature = sign_bytes(payload_bytes, mock_secret)
    
    # 5. Prepare Headers
    # CRITICAL: Your webhooks.py asks for 'x_hub_signature', 
    # so we send 'X-Hub-Signature' (standard casing).
    headers = {
        "X-Hub-Signature": signature,
        "Content-Type": "application/json"
    }
    
    # 6. Send Request
    # Path matches main.py prefix logic
    res = await client.post("/v1/api/webhooks/whatsapp", content=payload_bytes, headers=headers)
    
    # 7. Assert
    assert res.status_code == 200, f"Webhook failed: {res.text}"
    assert res.json() == {"status": "ok"}