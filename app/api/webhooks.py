# --- app/api/webhooks.py ---
from fastapi import APIRouter, Request, Header, HTTPException, Depends
import hmac, hashlib, os, json, logging
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.chat_service import ChatService

router = APIRouter()
logger = logging.getLogger(__name__)

APP_SECRET = os.getenv("WHATSAPP_APP_SECRET")

def verify_signature(body_bytes: bytes, signature_header: str) -> bool:
    if not signature_header or not APP_SECRET:
        return False
    algo, signature = signature_header.split("=", 1) if "=" in signature_header else (None, signature_header)
    mac = hmac.new(APP_SECRET.encode(), msg=body_bytes, digestmod=hashlib.sha256)
    return hmac.compare_digest(mac.hexdigest(), signature)

@router.post("/webhooks/whatsapp")
async def whatsapp_webhook(
    request: Request,
    x_hub_signature: str = Header(None),
    db: Session = Depends(get_db)
):
    # 1. Security: Verify Signature
    raw_body = await request.body()
    if not verify_signature(raw_body, x_hub_signature):
        logger.warning("Webhook signature verification failed.")
        raise HTTPException(status_code=401, detail="Invalid signature.")

    try:
        payload = json.loads(raw_body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON.")

    # 2. Process Payload
    chat_svc = ChatService(db)
    
    entries = payload.get("entry", [])
    for e in entries:
        for change in e.get("changes", []):
            val = change.get("value", {})
            
            # --- A. Handle Incoming Text Messages (Module 3) ---
            if "messages" in val:
                for m in val.get("messages", []):
                    # We only process text messages for now
                    if m.get("type") == "text":
                        sender = m.get("from")
                        text_body = m.get("text", {}).get("body")
                        
                        if sender and text_body:
                            # This saves to 'conversations' and 'chat_messages' tables
                            chat_svc.save_incoming(sender, text_body)
                            logger.info(f"Saved chat message from {sender}")

    return {"status": "ok"}