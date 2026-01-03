# app/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# Load database URL from centralized settings
DATABASE_URL = settings.DATABASE_URL

# Configure connection pooling to handle high throughput
# pool_size=20: Keep 20 connections open and ready.
# max_overflow=10: Allow 10 extra connections during spikes.
engine = create_engine(
    DATABASE_URL, 
    echo=False, 
    future=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW
)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create a Base class for our models to inherit from
Base = declarative_base()

def get_db():
    """
    Dependency for database session management.
    Ensures sessions are closed after request completion.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()