# app/api/webhooks.py
"""
Module: Webhook Handler
Context: Pod C - Integrations.

Receives, validates, and processes webhooks from WhatsApp (Meta).
Routes incoming data to ChatService (for messages) or StatusService (for receipts).
"""

from fastapi import APIRouter, Request, Header, HTTPException, Depends
import hmac, hashlib, json, logging
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.config import settings
from app.services.chat_service import ChatService
from app.services.status_service import StatusService 

router = APIRouter()
logger = logging.getLogger(__name__)

def verify_signature(body_bytes: bytes, signature_header: str) -> bool:
    """
    Validates the X-Hub-Signature header from Meta to ensure the request is authentic.
    Uses the app secret from settings.
    """
    if not signature_header or not settings.WHATSAPP_APP_SECRET:
        return False
    algo, signature = signature_header.split("=", 1) if "=" in signature_header else (None, signature_header)
    mac = hmac.new(settings.WHATSAPP_APP_SECRET.encode(), msg=body_bytes, digestmod=hashlib.sha256)
    return hmac.compare_digest(mac.hexdigest(), signature)

@router.post("/webhooks/whatsapp")
async def whatsapp_webhook(
    request: Request,
    x_hub_signature: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Main entry point for WhatsApp Webhooks.
    """
    # 1. Security: Verify Signature
    raw_body = await request.body()
    if not verify_signature(raw_body, x_hub_signature):
        logger.warning("Webhook signature verification failed.")
        raise HTTPException(status_code=401, detail="Invalid signature.")

    try:
        payload = json.loads(raw_body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON.")

    # 2. Initialize Services
    chat_svc = ChatService(db)
    status_svc = StatusService(db)

    # 3. Parse Entry List
    entries = payload.get("entry", [])
    for e in entries:
        for change in e.get("changes", []):
            val = change.get("value", {})
            
            # --- A. Handle Incoming Text Messages (Module 3) ---
            if "messages" in val:
                for m in val.get("messages", []):
                    if m.get("type") == "text":
                        sender = m.get("from")
                        text_body = m.get("text", {}).get("body")
                        
                        # Extract WhatsApp Message ID (WAMID)
                        wamid = m.get("id") 
                        
                        if sender and text_body:
                            # Pass wamid to service for linking
                            chat_svc.save_incoming(sender, text_body, message_id=wamid)
                            logger.info(f"Saved chat message {wamid} from {sender}")

            # --- B. Handle Status Updates (Module 6) ---
            if "statuses" in val:
                for s in val.get("statuses", []):
                    # Extract WAMID to match against ChatMessage
                    wamid = s.get("id")
                    status = s.get("status")
                    error = None
                    
                    # Extract error details if present
                    if "errors" in s:
                        error = str(s.get("errors"))
                    
                    # Update the reliability tracking table
                    status_svc.update_status(wamid, status, error)
                    logger.info(f"Updated status for msg {wamid} to {status}")

    return {"status": "ok"}