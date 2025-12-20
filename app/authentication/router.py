# app/authentication/router.py
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app import database
from app.core.config import settings
from . import crud, hashing, schemas

# --- CONFIGURATION ---

# OAuth2PasswordBearer tells FastAPI where to look for the token (in the Authorization header)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

# Create a new router for authentication endpoints
router = APIRouter(
    tags=["Authentication"]
)

# --- HELPER FUNCTIONS ---

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    """Creates a new JWT access token using centralized settings."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Fallback to the default expiration time from settings
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    
    # Sign the token using the secret key from settings
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(database.get_db)
):
    """
    Dependency to get the current user from a token.
    Validates the token signature and expiration.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Decode and verify the token using settings
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = schemas.TokenData(email=email)
    except JWTError:
        raise credentials_exception
    
    user = crud.get_user_by_email(db, email=token_data.email)
    if user is None:
        raise credentials_exception
    return user


# --- API ENDPOINTS ---

@router.post("/register", response_model=schemas.User, status_code=status.HTTP_201_CREATED)
def register_user(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    """
    Handles user registration. Hashes the password and saves the new user.
    """
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = hashing.hash_password(user.password)
    return crud.create_user(db=db, email=user.email, name=user.name, hashed_password=hashed_password)


@router.post("/token", response_model=schemas.Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(database.get_db)
):
    """
    Handles user login. Verifies credentials and returns a JWT access token.
    """
    user = crud.get_user_by_email(db, email=form_data.username)
    if not user or not hashing.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Use the expiration time defined in settings
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/users/me", response_model=schemas.User)
def read_users_me(current_user: schemas.User = Depends(get_current_user)):
    """
    A protected route to fetch the current authenticated user's details.
    """
    return current_user