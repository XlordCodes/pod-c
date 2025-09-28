import pytest
import hmac
import hashlib
import os
import json
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    return TestClient(app)

def test_webhook_rejects_invalid_signature(client):
    payload = {}
    response = client.post(
        "/api/webhooks/whatsapp",
        data=json.dumps(payload),
        headers={"X-Hub-Signature": "sha256=invalidsignature"}
    )
    assert response.status_code == 401
    assert "Invalid signature" in response.text

def test_webhook_accepts_valid_signature(client):
    secret = os.environ["WHATSAPP_APP_SECRET"]
    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "contacts": [{"wa_id": "919444285541"}],
                    "messages": [{
                        "id": "wamid.testmessage1",
                        "from": "919444285541",
                        "text": {"body": "Hello from test"}
                    }],
                    "metadata": {"phone_number_id": "769022132965312"}
                }
            }]
        }]
    }
    body_bytes = json.dumps(payload).encode()
    mac = hmac.new(secret.encode(), msg=body_bytes, digestmod=hashlib.sha256)
    signature = "sha256=" + mac.hexdigest()
    response = client.post(
        "/api/webhooks/whatsapp",
        content=body_bytes,
        headers={"X-Hub-Signature": signature}
    )
    print("DEBUG RESPONSE:", response.text)  # This will provide the true failure reason
    assert response.status_code == 200
    assert response.json()["status"] in ("ok", "duplicate")

