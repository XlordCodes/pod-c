# app/authentication/crud.py
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
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
    hashed_password: str
) -> models.User:
    """
    Creates a new user instance and adds it to the session.
    
    CRITICAL: This function performs a 'flush' to generate the ID but does NOT commit.
    The caller (Service/Router) is responsible for the final db.commit().
    
    SECURITY: tenant_id and role_id are explicitly set to None during registration.
    Tenant and role assignment is deferred to a secure workspace creation/invitation
    flow to ensure strict tenant isolation and prevent IDOR vulnerabilities.

    Args:
        db: The SQLAlchemy database session.
        name: The name of the user.
        email: The email of the user.
        hashed_password: The pre-hashed password for the user.

    Returns:
        The newly created User object (with populated ID).

    Raises:
        HTTPException: 400 error if email is already registered or if database
                       integrity constraint is violated (e.g., invalid foreign key reference).
    """
    # Explicit check for duplicate email before attempting insert
    existing_user = get_user_by_email(db, email)
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    
    db_user = models.User(
        name=name, 
        email=email, 
        hashed_password=hashed_password,
        # SECURITY: tenant_id and role_id are explicitly set to None.
        # Assignment is deferred to workspace creation/invitation flow
        # to prevent IDOR and privilege escalation vulnerabilities.
        tenant_id=None,
        role_id=None
    )
    
    try:
        db.add(db_user)
        
        # Flush sends the SQL INSERT to the transaction buffer.
        # This populates db_user.id and checks Unique Constraints (email).
        db.flush()
        
        return db_user
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Database integrity error: email already exists or invalid role/tenant ID provided."
        )