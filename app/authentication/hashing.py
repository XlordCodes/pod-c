# app/authentication/hashing.py
import bcrypt

def hash_password(password: str) -> str:
    """
    Hashes a plain-text password using bcrypt.
    """
    # bcrypt operates on bytes, so we encode the string
    pwd_bytes = password.encode('utf-8')
    
    # Generate a salt and hash the password
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    
    # Return as a string to store in the database
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain-text password against a hashed password.
    """
    try:
        pwd_bytes = plain_password.encode('utf-8')
        hash_bytes = hashed_password.encode('utf-8')
        
        # Check if the password matches
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        # If encoding fails or hash is invalid, return False
        return False