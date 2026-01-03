# tests/unit/test_security.py
import pytest
from app.core.security import encrypt_value, decrypt_value, SecurityException

def test_encryption_success():
    """
    Test standard encryption round-trip.
    Ensures that data is obfuscated and can be recovered.
    """
    secret = "TopSecret123"
    encrypted = encrypt_value(secret)
    
    # Verify strict inequality (encryption must change the string)
    assert encrypted != secret
    # Verify decryption restores the original
    assert decrypt_value(encrypted) == secret

def test_encryption_failure_raises_exception(mocker):
    """
    Verify that if the underlying encryption library fails (e.g., hardware error),
    we raise a custom SecurityException instead of leaking the raw error.
    """
    # Mock the cipher_suite used inside security.py to raise an Exception
    mock_cipher = mocker.patch("app.core.security.cipher_suite")
    mock_cipher.encrypt.side_effect = Exception("Hardware/Library Error")
    
    with pytest.raises(SecurityException) as exc:
        encrypt_value("data")
    
    # Check that our custom error message is present
    assert "Data encryption failed" in str(exc.value)

def test_decryption_failure_raises_exception():
    """
    Verify that invalid tokens/tampered data raise SecurityException.
    """
    invalid_token = "invalid-token-string"
    
    # The real Fernet library raises InvalidToken for garbage input.
    # Our wrapper should catch that and re-raise SecurityException.
    with pytest.raises(SecurityException) as exc:
        decrypt_value(invalid_token)
    
    assert "Data decryption failed" in str(exc.value)