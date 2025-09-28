import pytest
import hmac
import hashlib
import os
import json
from fastapi.testclient import TestClient
from app.models import Message
from app.database import SessionLocal
from app.main import app

@pytest.fixture
def client():
    return TestClient(app)

def test_webhook_creates_message(client):
    secret = os.environ["WHATSAPP_APP_SECRET"]
    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "contacts": [{"wa_id": "919444285541"}],
                    "messages": [{
                        "id": "wamid.demo456789",
                        "from": "919444285541",
                        "text": {"body": "Integration test message"}
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
    assert response.status_code == 200

    db = SessionLocal()
    try:
        msg = db.query(Message).filter_by(message_id="wamid.demo456789").first()
        assert msg is not None
        assert msg.from_number == "919444285541"
        assert msg.text == "Integration test message"
    finally:
        db.close()
