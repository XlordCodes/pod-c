# app/authentication/crud.py
from sqlalchemy.orm import Session
from typing import Optional, List
from .. import models 

def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    """
    Fetches a single user from the database by their email address.

    Args:
        db: The SQLAlchemy database session.
        email: The email of the user to retrieve.

    Returns:
        The User object if found, otherwise None.
    """
    return db.query(models.User).filter(models.User.email == email).first()


def get_all_users(db: Session) -> List[models.User]:
    """
    Fetches all users from the database.

    Args:
        db: The SQLAlchemy database session.

    Returns:
        A list of all User objects.
    """
    return db.query(models.User).all()


def create_user(
    db: Session, 
    name: str, 
    email: str, 
    hashed_password: str,
    tenant_id: Optional[int] = None,
    role_id: Optional[int] = None
) -> models.User:
    """
    Creates a new user instance and adds it to the session.
    
    CRITICAL: This function performs a 'flush' to generate the ID but does NOT commit.
    The caller (Service/Router) is responsible for the final db.commit().

    Args:
        db: The SQLAlchemy database session.
        name: The name of the user.
        email: The email of the user.
        hashed_password: The pre-hashed password for the user.
        tenant_id: Optional ID for the tenant organization.
        role_id: Optional ID for the user's role (admin/staff).

    Returns:
        The newly created User object (with populated ID).
    """
    db_user = models.User(
        name=name, 
        email=email, 
        hashed_password=hashed_password,
        # --- MAP NEW FIELDS ---
        tenant_id=tenant_id,
        role_id=role_id
    )
    db.add(db_user)
    
    # Flush sends the SQL INSERT to the transaction buffer.
    # This populates db_user.id and checks Unique Constraints (email).
    # If this fails, the caller can catch the error and rollback.
    db.flush()
    
    return db_user