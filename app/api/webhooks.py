# app/api/webhooks.py
"""
Module: Webhook Handler
Context: Pod C - Integrations.

Receives, validates, and processes webhooks from WhatsApp (Meta).
Routes incoming data to:
1. ChatService (Module 3): For storing incoming customer messages.
2. StatusService (Module 6): For tracking delivery receipts (Sent/Delivered/Read).

SECURITY HARDENING:
- Timing-attack resistant signature verification using hmac.compare_digest
- Pydantic-based input validation for all incoming payloads
- Text length sanitization to prevent DoS attacks
- Graceful handling of malformed headers and invalid payloads
"""

from fastapi import APIRouter, Request, Header, HTTPException, Depends, Query
import hmac
import hashlib
import json
import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, validator, ValidationError

# --- Core Imports ---
from app.database import get_db
from app.core.config import settings

# --- Service Imports ---
from app.services.chat_service import ChatService
from app.services.status_service import StatusService 

router = APIRouter()
logger = logging.getLogger(__name__)

# ============================================================================
# SECURITY CONSTANTS
# ============================================================================
MAX_TEXT_LENGTH = 4096  # Maximum allowed text body length to prevent DoS


# ============================================================================
# PYDANTIC MODELS FOR INPUT VALIDATION
# ============================================================================

class WhatsAppTextContent(BaseModel):
    """Text content within a WhatsApp message."""
    body: str = Field(..., max_length=MAX_TEXT_LENGTH)
    
    @validator('body')
    def sanitize_text(cls, v):
        """Ensure text body doesn't exceed safe limits."""
        if len(v) > MAX_TEXT_LENGTH:
            raise ValueError(f'Text body exceeds maximum length of {MAX_TEXT_LENGTH} characters')
        return v


class WhatsAppMessage(BaseModel):
    """
    Validates the structure of an incoming WhatsApp message.
    
    Security: Enforces strict schema validation to prevent malformed data injection.
    """
    id: str = Field(..., description="WhatsApp Message ID (WAMID)")
    type: str = Field(..., description="Message type (text, image, audio, etc.)")
    from_: str = Field(..., alias="from", description="Sender's phone number")
    timestamp: str = Field(..., description="Unix timestamp as string")
    text: Optional[WhatsAppTextContent] = None
    
    class Config:
        # Allow 'from' field to be populated from 'from' key in JSON
        populate_by_name = True
    
    @validator('from_')
    def validate_phone_number(cls, v):
        """Basic validation for phone number format."""
        if not v or not v.strip():
            raise ValueError('Phone number cannot be empty')
        # WhatsApp phone numbers are typically numeric with country code
        if not v.replace('+', '').isdigit():
            raise ValueError('Invalid phone number format')
        return v
    
    @validator('type')
    def validate_message_type(cls, v):
        """Ensure message type is recognized."""
        allowed_types = {'text', 'image', 'audio', 'video', 'document', 'location', 'contacts', 'button', 'interactive'}
        if v not in allowed_types:
            logger.warning(f"Unknown message type received: {v}")
        return v


class WhatsAppStatusUpdate(BaseModel):
    """
    Validates the structure of a WhatsApp status update (delivery receipt).
    """
    id: str = Field(..., description="WhatsApp Message ID (WAMID)")
    status: str = Field(..., description="Status: sent, delivered, read, failed")
    timestamp: str = Field(..., description="Unix timestamp as string")
    recipient_id: Optional[str] = None
    errors: Optional[List[Dict[str, Any]]] = None
    
    @validator('status')
    def validate_status(cls, v):
        """Ensure status is a recognized value."""
        allowed_statuses = {'sent', 'delivered', 'read', 'failed'}
        if v not in allowed_statuses:
            logger.warning(f"Unknown status received: {v}")
        return v


class WhatsAppValue(BaseModel):
    """
    The 'value' object within a webhook change notification.
    """
    messaging_product: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    contacts: Optional[List[Dict[str, Any]]] = None
    messages: Optional[List[WhatsAppMessage]] = None
    statuses: Optional[List[WhatsAppStatusUpdate]] = None


class WhatsAppChange(BaseModel):
    """
    A single change notification within an entry.
    """
    field: str
    value: WhatsAppValue


class WhatsAppEntry(BaseModel):
    """
    An entry in the webhook payload (Meta can batch multiple entries).
    """
    id: str
    changes: List[WhatsAppChange]


class WhatsAppWebhookPayload(BaseModel):
    """
    Root-level validation for the entire WhatsApp webhook payload.
    
    Security: This model enforces strict schema validation before any processing occurs.
    Invalid payloads are rejected early to prevent injection attacks.
    """
    object: str = Field(..., description="Should be 'whatsapp_business_account'")
    entry: List[WhatsAppEntry]
    
    @validator('object')
    def validate_object_type(cls, v):
        """Ensure this is a WhatsApp webhook."""
        if v != 'whatsapp_business_account':
            raise ValueError(f"Invalid object type: {v}. Expected 'whatsapp_business_account'")
        return v


# ============================================================================
# SECURITY FUNCTIONS
# ============================================================================

def verify_signature(body_bytes: bytes, signature_header: Optional[str]) -> bool:
    """
    Validates the X-Hub-Signature-256 header from Meta to ensure the request is authentic.
    Meta signs the request body using our App Secret (HMAC-SHA256).
    
    SECURITY IMPROVEMENTS:
    1. Uses hmac.compare_digest() to prevent timing attacks
    2. Handles malformed headers gracefully without crashing
    3. Validates header format before processing
    4. Constant-time comparison of signatures
    
    Args:
        body_bytes: Raw request body as bytes
        signature_header: Value of X-Hub-Signature-256 header
        
    Returns:
        bool: True if signature is valid, False otherwise
    """
    # Reject if no signature provided
    if not signature_header:
        logger.warning("⚠️ No signature header provided")
        return False
    
    # Reject if app secret is not configured
    if not settings.WHATSAPP_APP_SECRET:
        logger.error("CRITICAL: WHATSAPP_APP_SECRET is not set. Cannot verify webhooks.")
        return False
    
    # Parse header format: "sha256=<hex_signature>"
    # Handle malformed headers gracefully
    try:
        if "=" not in signature_header:
            logger.warning(f"⚠️ Malformed signature header: missing '=' delimiter")
            return False
        
        parts = signature_header.split("=", 1)
        if len(parts) != 2:
            logger.warning(f"⚠️ Malformed signature header: invalid format")
            return False
        
        algo, received_signature = parts
        
        # Validate algorithm
        if algo != "sha256":
            logger.warning(f"⚠️ Unsupported signature algorithm: {algo}")
            return False
        
        # Validate signature is hex string
        if not received_signature or not all(c in '0123456789abcdefABCDEF' for c in received_signature):
            logger.warning(f"⚠️ Invalid signature format: not a valid hex string")
            return False
        
    except Exception as e:
        logger.error(f"❌ Error parsing signature header: {e}")
        return False
    
    # Calculate expected signature
    try:
        mac = hmac.new(
            settings.WHATSAPP_APP_SECRET.encode('utf-8'), 
            msg=body_bytes, 
            digestmod=hashlib.sha256
        )
        expected_signature = mac.hexdigest()
        
        # SECURITY: Use constant-time comparison to prevent timing attacks
        # This prevents attackers from using response time to guess the signature
        is_valid = hmac.compare_digest(expected_signature, received_signature.lower())
        
        if not is_valid:
            logger.warning(f"⚠️ Signature mismatch - potential tampering detected")
        
        return is_valid
        
    except Exception as e:
        logger.error(f"❌ Error computing signature: {e}")
        return False


# ============================================================================
# WEBHOOK ENDPOINTS
# ============================================================================

@router.post("/webhooks/whatsapp")
async def whatsapp_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
    db: Session = Depends(get_db)
):
    """
    Main entry point for WhatsApp Cloud API Webhooks.
    
    SECURITY FEATURES:
    1. Timing-attack resistant signature verification
    2. Pydantic-based schema validation
    3. Text length sanitization (max 4096 chars)
    4. Graceful error handling with 200 OK to prevent Meta retries
    5. Comprehensive logging for security auditing
    """
    # ========================================================================
    # STEP 1: SIGNATURE VERIFICATION (Critical Security Check)
    # ========================================================================
    # We must read the raw bytes for HMAC verification
    raw_body = await request.body()
    
    if not verify_signature(raw_body, x_hub_signature_256):
        logger.warning(
            f"⚠️ SECURITY ALERT: Webhook signature verification failed. "
            f"IP: {request.client.host if request.client else 'unknown'}"
        )
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # ========================================================================
    # STEP 2: JSON PARSING
    # ========================================================================
    try:
        payload_dict = json.loads(raw_body)
    except json.JSONDecodeError as e:
        logger.error(f"❌ Received invalid JSON in webhook: {e}")
        # Return 200 OK to prevent Meta from retrying invalid payloads
        return {"status": "error", "message": "Invalid JSON"}
    
    # ========================================================================
    # STEP 3: SCHEMA VALIDATION (Pydantic)
    # ========================================================================
    try:
        # Validate entire payload structure using Pydantic
        validated_payload = WhatsAppWebhookPayload(**payload_dict)
        logger.info(f"✅ Webhook payload validated successfully")
        
    except ValidationError as e:
        # Log validation errors for security auditing
        logger.error(
            f"❌ SECURITY: Invalid webhook payload schema. "
            f"Errors: {e.errors()}"
        )
        # Return 200 OK to prevent Meta from retrying invalid payloads indefinitely
        # This prevents DoS via repeated invalid payload submissions
        return {"status": "error", "message": "Invalid payload schema"}
    
    except Exception as e:
        logger.error(f"❌ Unexpected error during validation: {e}")
        return {"status": "error", "message": "Validation failed"}
    
    # ========================================================================
    # STEP 4: INITIALIZE SERVICES
    # ========================================================================
    chat_svc = ChatService(db)
    status_svc = StatusService(db)
    
    # ========================================================================
    # STEP 5: PROCESS VALIDATED ENTRIES
    # ========================================================================
    for entry in validated_payload.entry:
        for change in entry.changes:
            val = change.value
            
            # --- A. Handle Incoming Messages (User -> Bot) ---
            if val.messages:
                for msg in val.messages:
                    try:
                        # Process text messages
                        # Note: Text length is already validated by Pydantic (max 4096 chars)
                        if msg.type == "text" and msg.text:
                            sender = msg.from_
                            text_body = msg.text.body
                            wamid = msg.id
                            
                            # Additional sanitization check (defense in depth)
                            if len(text_body) > MAX_TEXT_LENGTH:
                                logger.warning(
                                    f"⚠️ SECURITY: Text body exceeds max length. "
                                    f"Truncating message {wamid}"
                                )
                                text_body = text_body[:MAX_TEXT_LENGTH]
                            
                            # Save to DB (ChatService handles Contact lookup logic)
                            chat_svc.save_incoming(sender, text_body, message_id=wamid)
                            logger.info(f"📩 Saved message {wamid} from {sender}")
                        
                        # Future: Add handlers for other message types (image, audio, etc.)
                        elif msg.type in {'image', 'audio', 'video', 'document'}:
                            logger.info(f"ℹ️ Received {msg.type} message {msg.id} - handler not yet implemented")
                        
                    except Exception as e:
                        logger.error(
                            f"❌ Failed to process message {msg.id}: {e}",
                            exc_info=True
                        )
                        # Continue processing other messages
            
            # --- B. Handle Status Updates (Sent/Delivered/Read) ---
            if val.statuses:
                for status_update in val.statuses:
                    try:
                        wamid = status_update.id
                        status_state = status_update.status
                        
                        # Extract error info if delivery failed
                        error_data = None
                        if status_update.errors:
                            error_data = json.dumps(status_update.errors)
                        
                        # Update the BulkMessage or ChatMessage status
                        status_svc.update_status(wamid, status_state, error_data)
                        logger.debug(f"📊 Status update for {wamid}: {status_state}")
                        
                    except Exception as e:
                        logger.error(
                            f"❌ Failed to update status for {status_update.id}: {e}",
                            exc_info=True
                        )
                        # Continue processing other status updates
    
    # ========================================================================
    # STEP 6: ACKNOWLEDGE RECEIPT
    # ========================================================================
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
    
    SECURITY: Requires WHATSAPP_VERIFY_TOKEN to be configured in environment.
    No fallback is provided - the application will fail to start if missing.
    """
    # SECURITY FIX: No fallback allowed. Token must be explicitly configured.
    if not settings.WHATSAPP_VERIFY_TOKEN:
        logger.error("CRITICAL: WHATSAPP_VERIFY_TOKEN is not configured")
        raise HTTPException(status_code=500, detail="Server misconfiguration")
    
    VERIFY_TOKEN = settings.WHATSAPP_VERIFY_TOKEN
    
    # Use constant-time comparison for verify token as well
    if hub_mode == "subscribe" and hub_verify_token and hmac.compare_digest(hub_verify_token, VERIFY_TOKEN):
        logger.info("✅ Webhook verified successfully.")
        # Meta expects the challenge string returned as plain text (integer-like string)
        return int(hub_challenge) if hub_challenge and hub_challenge.isdigit() else hub_challenge
    
    logger.warning("⚠️ Webhook verification failed.")
    raise HTTPException(status_code=403, detail="Verification failed")
