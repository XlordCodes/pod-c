# app/database.py
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from app.core.config import settings
from app.core.context import get_tenant_id

# Load database URL from centralized settings
DATABASE_URL = settings.DATABASE_URL

# Configure connection pooling
engine = create_engine(
    DATABASE_URL, 
    echo=False, 
    future=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True  # Production Fix: Auto-reconnect if DB closes connection
)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create a Base class for our models to inherit from
Base = declarative_base()

# --- RLS (Row Level Security) Enforcement Hook ---
@event.listens_for(SessionLocal, "after_begin")
def set_tenant_context(session: Session, transaction, connection):
    """
    Injects the current tenant_id into the PostgreSQL session context
    whenever a new transaction begins.
    
    This command: SET app.current_tenant = '123';
    allows RLS policies in Postgres to filter data automatically:
    USING (tenant_id = current_setting('app.current_tenant')::int)
    """
    tenant_id = get_tenant_id()
    if tenant_id is not None:
        connection.execute(
            text("SELECT set_config('app.current_tenant', :tenant_id, false)"), 
            {"tenant_id": str(tenant_id)}
        )

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