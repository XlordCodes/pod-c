# app/api/webhooks.py
"""
Module: Webhook Handler
Context: Pod C - Integrations.

Receives, validates, and processes webhooks from WhatsApp (Meta).
Routes incoming data to:
1. ChatService (Module 3): For storing incoming customer messages.
2. StatusService (Module 6): For tracking delivery receipts (Sent/Delivered/Read).
"""

from fastapi import APIRouter, Request, Header, HTTPException, Depends, Query
import hmac
import hashlib
import json
import logging
from sqlalchemy.orm import Session

# --- Core Imports ---
from app.database import get_db
from app.core.config import settings

# --- Service Imports ---
from app.services.chat_service import ChatService
from app.services.status_service import StatusService 

router = APIRouter()
logger = logging.getLogger(__name__)

def verify_signature(body_bytes: bytes, signature_header: str) -> bool:
    """
    Validates the X-Hub-Signature header from Meta to ensure the request is authentic.
    Meta signs the request body using our App Secret (HMAC-SHA256).
    """
    if not signature_header:
        # If no signature is provided, strictly reject in production.
        # In dev, you might want to relax this, but it's safer to always enforce it.
        return False
        
    if not settings.WHATSAPP_APP_SECRET:
        logger.error("WHATSAPP_APP_SECRET is not set. Cannot verify webhooks.")
        return False

    # Header format: "sha256=..."
    algo, signature = signature_header.split("=", 1) if "=" in signature_header else (None, signature_header)
    
    if algo != "sha256":
        return False

    # Calculate expected signature
    mac = hmac.new(
        settings.WHATSAPP_APP_SECRET.encode(), 
        msg=body_bytes, 
        digestmod=hashlib.sha256
    )
    
    # Secure comparison to prevent timing attacks
    return hmac.compare_digest(mac.hexdigest(), signature)

@router.post("/webhooks/whatsapp")
async def whatsapp_webhook(
    request: Request,
    x_hub_signature: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Main entry point for WhatsApp Cloud API Webhooks.
    """
    # 1. Security Check
    # We must read the raw bytes for HMAC verification
    raw_body = await request.body()
    
    if not verify_signature(raw_body, x_hub_signature):
        logger.warning(f"⚠️ Webhook signature verification failed. IP: {request.client.host}")
        raise HTTPException(status_code=401, detail="Invalid signature")

    # 2. Parse Payload
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        logger.error("Received invalid JSON in webhook.")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # 3. Initialize Services
    chat_svc = ChatService(db)
    status_svc = StatusService(db)

    # 4. Process Entries
    # Meta sends updates in a list of 'entry' objects
    entries = payload.get("entry", [])
    
    for entry in entries:
        for change in entry.get("changes", []):
            val = change.get("value", {})
            
            # --- A. Handle Incoming Messages (User -> Bot) ---
            if "messages" in val:
                for msg in val.get("messages", []):
                    try:
                        # We currently support text messages. 
                        # Future: Add image/audio handlers here.
                        if msg.get("type") == "text":
                            sender = msg.get("from")
                            text_body = msg.get("text", {}).get("body")
                            wamid = msg.get("id")
                            
                            if sender and text_body:
                                # Save to DB (ChatService handles Contact lookup logic)
                                chat_svc.save_incoming(sender, text_body, message_id=wamid)
                                logger.info(f"📩 Saved message {wamid} from {sender}")
                                
                    except Exception as e:
                        logger.error(f"❌ Failed to process message {msg.get('id')}: {e}")
                        # We continue loop so one bad message doesn't block others

            # --- B. Handle Status Updates (Sent/Delivered/Read) ---
            if "statuses" in val:
                for status_update in val.get("statuses", []):
                    try:
                        wamid = status_update.get("id")
                        status_state = status_update.get("status")
                        
                        # Extract error info if delivery failed
                        error_data = None
                        if "errors" in status_update:
                            error_data = str(status_update.get("errors"))
                        
                        # Update the BulkMessage or ChatMessage status
                        status_svc.update_status(wamid, status_state, error_data)
                        logger.debug(f"📊 Status update for {wamid}: {status_state}")
                        
                    except Exception as e:
                        logger.error(f"❌ Failed to update status for {status_update.get('id')}: {e}")

    # 5. Acknowledge Receipt
    # We must return 200 OK immediately, or Meta will retry sending the webhook.
    return {"status": "ok"}

@router.get("/webhooks/whatsapp")
def verify_webhook(
    request: Request,
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge")
):
    """
    Verification endpoint used by Meta when you first configure the webhook URL.
    """
    # In production, use a secure random string from settings
    VERIFY_TOKEN = settings.WHATSAPP_VERIFY_TOKEN or "my_secure_token"

    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        logger.info("✅ Webhook verified successfully.")
        # Meta expects the challenge string returned as plain text (integer-like string)
        return int(hub_challenge) if hub_challenge.isdigit() else hub_challenge
    
    logger.warning("⚠️ Webhook verification failed.")
    raise HTTPException(status_code=403, detail="Verification failed")