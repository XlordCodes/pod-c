# app/api/whatsapp.py
"""
Module: WhatsApp API
Context: Pod C - Integrations

Exposes endpoints to send WhatsApp messages.
Delegates actual transmission logic to the robust 'whatsapp_client'.

SECURITY: All endpoints require JWT authentication.
"""

import logging
from typing import Optional, List, Any
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field

# Import the unified client we just created
from app.integrations.whatsapp_client import whatsapp_client
from app.authentication.router import get_current_user
from app.models.auth import User

router = APIRouter()
logger = logging.getLogger(__name__)

class WhatsAppTemplateSendIn(BaseModel):
    """
    Request schema for sending a template message.
    """
    to: str = Field(..., description="Target WhatsApp number (e.g., '15550123456')")
    template_name: str = Field(..., description="The approved template name (e.g., 'hello_world')")
    language_code: str = Field(default="en_US", description="Template language code")
    
    # Flexible list for template variables (text, currency, etc.)
    parameters: Optional[List[Any]] = Field(default=None, description="List of variable values for the template body")

@router.post("/whatsapp/send-template", status_code=status.HTTP_200_OK)
async def send_whatsapp_template(
    payload: WhatsAppTemplateSendIn,
    current_user: User = Depends(get_current_user)
):
    """
    Sends a WhatsApp template message.
    
    Uses the asynchronous WhatsApp client to ensure non-blocking I/O
    and automatic retries for transient network failures.
    
    SECURITY: Requires valid JWT authentication.
    
    Args:
        payload (WhatsAppTemplateSendIn): The template message details.
        current_user (User): The authenticated user making the request.
        
    Returns:
        dict: Status and provider response.
        
    Raises:
        HTTPException 500: If the message fails to send.
    """
    try:
        # Delegate to the integration client
        # Note: The client handles authentication and URL construction
        response = await whatsapp_client.send_template_async(
            to_number=payload.to,
            template_name=payload.template_name,
            language=payload.language_code,
            components=payload.parameters
        )
        
        return {
            "status": "sent", 
            "provider_response": response
        }
        
    except Exception as e:
        logger.error(f"WhatsApp API Error: {str(e)}")
        # Raise 500 but include the error message for debugging 
        # (In strict prod, mask this)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to send message: {str(e)}"
        )
