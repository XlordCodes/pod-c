# app/authentication/hashing.py
from passlib.context import CryptContext

# Configure Passlib to use bcrypt, a strong and standard hashing algorithm.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Hashes a plain-text password using bcrypt.

    Args:
        password: The plain-text password to hash.

    Returns:
        The hashed password string.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain-text password against a hashed password.

    Args:
        plain_password: The plain-text password from the user.
        hashed_password: The hashed password stored in the database.

    Returns:
        True if the passwords match, False otherwise.
    """
    return pwd_context.verify(plain_password, hashed_password)
