# app/core/security.py
import logging
from cryptography.fernet import Fernet
from app.core.config import settings

logger = logging.getLogger(__name__)

class SecurityException(Exception):
    """Custom exception for security/encryption failures."""
    pass

# Initialize cipher suite
try:
    cipher_suite = Fernet(settings.ENCRYPTION_KEY)
except Exception as e:
    # Critical error: App cannot function safely without this.
    logger.critical(f"Security Init Failed: Encryption key is invalid or missing. {e}")
    cipher_suite = None

def encrypt_value(value: str) -> str:
    """
    Encrypts a plain string into a Fernet token.
    Raises SecurityException on failure to prevent data loss.
    """
    if value is None:
        return None
    
    if not cipher_suite:
        logger.error("Attempted to encrypt without a valid key.")
        raise SecurityException("Encryption service unavailable.")
        
    try:
        encrypted_bytes = cipher_suite.encrypt(value.encode("utf-8"))
        return encrypted_bytes.decode("utf-8")
    except Exception as e:
        logger.error(f"Encryption processing failed: {e}")
        raise SecurityException("Data encryption failed.")

def decrypt_value(token: str) -> str:
    """
    Decrypts a Fernet token back to the original string.
    """
    if token is None:
        return None
    
    if not cipher_suite:
        logger.error("Attempted to decrypt without a valid key.")
        raise SecurityException("Encryption service unavailable.")
        
    try:
        decrypted_bytes = cipher_suite.decrypt(token.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except Exception as e:
        logger.error(f"Decryption processing failed: {e}")
        # In rare cases (key rotation), you might want to return None, 
        # but for a strict CRM, we raise an error to investigate.
        raise SecurityException("Data decryption failed.")