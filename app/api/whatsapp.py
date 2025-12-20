# app/api/whatsapp.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import httpx
from app.core.config import settings

router = APIRouter()

class WhatsAppTemplateSendIn(BaseModel):
    to: str  # WhatsApp number as string, e.g., '919876543210'
    template_name: str  # WhatsApp approved template name
    language_code: Optional[str] = "en_US"  # or your default
    parameters: Optional[list] = None  # Text parameters for the template

@router.post("/whatsapp/send-template")
async def send_whatsapp_template(payload: WhatsAppTemplateSendIn):
    """
    Sends a WhatsApp template message using credentials from settings.
    """
    # Validate credentials from settings
    access_token = settings.WHATSAPP_TOKEN
    phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
    
    if not access_token or not phone_number_id:
        raise HTTPException(status_code=500, detail="Missing WhatsApp credentials in configuration.")

    url = (
        f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"
    )
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    components = []
    if payload.parameters:
        components = [
            {
                "type": "body",
                "parameters": [{"type": "text", "text": str(p)} for p in payload.parameters],
            }
        ]
    data = {
        "messaging_product": "whatsapp",
        "to": payload.to,
        "type": "template",
        "template": {
            "name": payload.template_name,
            "language": {"code": payload.language_code},
            "components": components,
        },
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=data)
    
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.json())
    return {"status": "sent", "whatsapp_response": resp.json()}