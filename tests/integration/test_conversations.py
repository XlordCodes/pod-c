# tests/integration/test_conversations.py
import pytest
import uuid
import hmac
import hashlib
import json
from httpx import AsyncClient
from app.core.config import settings

# Mark all tests in this module as asyncio
pytestmark = pytest.mark.asyncio

# -----------------------------------------------------------------------------
# TESTS
# -----------------------------------------------------------------------------

async def test_get_conversations_empty_initially(client: AsyncClient, auth_headers):
    """
    Verify that a new user sees an empty conversation list initially.
    """
    res = await client.get("/v1/api/chat/conversations", headers=auth_headers)
    assert res.status_code == 200, f"Failed to list conversations: {res.text}"
    assert res.json() == []

async def test_create_and_list_message(client: AsyncClient, auth_headers):
    """
    1. Create a Message via the Messages API.
    2. Retrieve it via the Messages API to confirm persistence.
    """
    # 1. Create a Message
    payload = {
        "message_type": "text",
        "from_number": "+919988776655",
        "text": "Hello, is this available?"
    }
    
    # Path: /v1/api/messages
    res = await client.post("/v1/api/messages", json=payload, headers=auth_headers)
    assert res.status_code == 200, f"Message creation failed: {res.text}"
    msg_id = res.json()["id"]

    # 2. List Messages to confirm it appears
    # Note: Use 'params' dict so httpx encodes the '+' symbol correctly (%2B)
    list_res = await client.get(
        "/v1/api/messages", 
        params={"from_number": payload['from_number']}, 
        headers=auth_headers
    )
    assert list_res.status_code == 200
    
    messages = list_res.json()
    assert len(messages) >= 1
    assert messages[0]["text"] == payload["text"]
    assert messages[0]["id"] == msg_id

async def test_webhook_flow_creates_conversation(client: AsyncClient, auth_headers):
    """
    Integration: 
    1. Simulate an incoming WhatsApp Webhook.
    2. Verify data via the Chat API.
    """
    # 1. Simulate Webhook
    customer_number = f"91{uuid.uuid4().int}"[:12]
    
    webhook_payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": customer_number,
                        "id": f"wamid.{uuid.uuid4().hex}",
                        "type": "text",
                        "text": {"body": "I want to buy a cake"}
                    }]
                }
            }]
        }]
    }
    
    # Sign request (HMAC-SHA256)
    payload_bytes = json.dumps(webhook_payload).encode("utf-8")
    secret = settings.WHATSAPP_APP_SECRET.encode()
    signature = hmac.new(secret, payload_bytes, hashlib.sha256).hexdigest()
    
    headers = {
        "X-Hub-Signature": f"sha256={signature}",
        "Content-Type": "application/json"
    }

    # Send Webhook
    res = await client.post("/v1/api/webhooks/whatsapp", content=payload_bytes, headers=headers)
    assert res.status_code == 200

    # 2. Verify Conversation Created
    # Assuming chat_service creates a conversation accessible via this endpoint
    chat_res = await client.get("/v1/api/chat/conversations", headers=auth_headers)
    assert chat_res.status_code == 200
    
    conversations = chat_res.json()
    my_convo = next((c for c in conversations if c.get("customer_number") == customer_number), None)
    
    assert my_convo is not None, "Webhook did not create a conversation!"
    
    # 3. Verify Message Content
    msg_res = await client.get(f"/v1/api/chat/conversations/{my_convo['id']}", headers=auth_headers)
    assert msg_res.status_code == 200
    
    messages = msg_res.json()
    assert len(messages) > 0
    assert messages[0]["text"] == "I want to buy a cake"