from fastapi import APIRouter, Request, Header, HTTPException, Depends
import hmac, hashlib, os, json
from app.database import get_db
from app.models import Message
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

router = APIRouter()

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
    raw_body = await request.body()
    if not verify_signature(raw_body, x_hub_signature):
        raise HTTPException(status_code=401, detail="Invalid signature.")

    try:
        payload = json.loads(raw_body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON.")

    entries = payload.get("entry", [])
    try:
        for e in entries:
            for change in e.get("changes", []):
                val = change.get("value", {})
                messages = val.get("messages", [])
                for m in messages:
                    msg = Message(
                        from_number=m.get("from"),
                        to_number=val.get("metadata", {}).get("phone_number_id"),
                        message_id=m.get("id"),
                        payload=m,  # store entire message JSON
                        text=m.get("text", {}).get("body"),
                    )
                    db.add(msg)
        db.commit()
    except IntegrityError:
        db.rollback()
        # Duplicate (idempotency): just skip
        return {"status": "duplicate"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"DB error: {str(e)}")

    return {"status": "ok"}

