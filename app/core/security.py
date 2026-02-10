# app/core/security.py
"""
Module: Security & Encryption Utilities
Context: Core Infrastructure

Provides AES-GCM encryption for sensitive fields (e.g., National IDs, API Keys).
Uses the 'cryptography' library (Fernet) for symmetric encryption.

CRITICAL: This module enforces a "Fail-Fast" policy. 
If the encryption key is invalid, the application will refuse to start.
"""

import logging
from cryptography.fernet import Fernet
from app.core.config import settings

logger = logging.getLogger(__name__)

class SecurityException(Exception):
    """
    Custom exception for security/encryption failures.
    Catch this in Service layers to handle data access errors gracefully.
    """
    pass

# --- INITIALIZATION ---
# Attempt to initialize the cipher suite at module load time.
# This ensures we catch configuration errors immediately during startup.

try:
    if not settings.ENCRYPTION_KEY:
        raise ValueError("ENCRYPTION_KEY is missing from configuration.")
        
    # Fernet requires a 32-byte url-safe base64-encoded key.
    # If the key format is invalid, this will raise a ValueError/TypeError.
    cipher_suite = Fernet(settings.ENCRYPTION_KEY)
    
except Exception as e:
    # Log the critical error to ensuring it appears in system logs/Sentry
    logger.critical(f"🔥 SECURITY FATAL ERROR: Encryption key is invalid. {e}")
    
    # Re-raise as a RuntimeError to stop the ASGI server (Uvicorn) from starting.
    # We generally do NOT want the app to run in an insecure/broken state.
    raise RuntimeError(f"Application cannot start without valid security config: {e}")


# --- UTILITIES ---

def encrypt_value(value: str) -> str:
    """
    Encrypts a plain text string into a URL-safe base64-encoded Fernet token.
    
    Args:
        value (str): The sensitive string to encrypt.
        
    Returns:
        str: The encrypted token string.
        None: If the input value is None.
        
    Raises:
        SecurityException: If encryption fails for any reason.
    """
    if value is None:
        return None
    
    try:
        # Fernet expects bytes, so we encode utf-8
        encrypted_bytes = cipher_suite.encrypt(value.encode("utf-8"))
        # Return as string for database storage
        return encrypted_bytes.decode("utf-8")
        
    except Exception as e:
        logger.error(f"Encryption processing failed: {str(e)}")
        raise SecurityException("Data encryption failed due to internal error.")

def decrypt_value(token: str) -> str:
    """
    Decrypts a Fernet token back to the original plain text string.
    
    Args:
        token (str): The encrypted token to decrypt.
        
    Returns:
        str: The decrypted plain text.
        None: If the input token is None.
        
    Raises:
        SecurityException: If the token is invalid, tampered with, or expired.
    """
    if token is None:
        return None
    
    try:
        # Fernet expects bytes
        decrypted_bytes = cipher_suite.decrypt(token.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
        
    except Exception as e:
        logger.error(f"Decryption processing failed: {str(e)}")
        # We raise a generic security exception to avoid leaking crypto details
        raise SecurityException("Data decryption failed. Token may be invalid or corrupted.")