# tests/conftest.py
import pytest
import pytest_asyncio
from dotenv import load_dotenv
from unittest.mock import MagicMock

# 1. Force load .env
load_dotenv()

from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base, get_db
from app.core.config import settings

# Import models to ensure they are registered with Base.metadata
from app.models import User, BulkJob, BulkMessage, Contact, Conversation, ChatMessage, AuditLog, EmailQueue
from app.models import MessageEmbedding
from app.models import MessageStatus
from app.models import ReplySuggestion

# --- Database Setup ---
if "sqlite" in settings.DATABASE_URL:
    print(f"WARNING: Tests are running against SQLite: {settings.DATABASE_URL}")
else:
    print(f"INFO: Tests are running against PostgreSQL: {settings.DATABASE_URL}")

# Create Engine
engine = create_engine(settings.DATABASE_URL, pool_size=5, max_overflow=0)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """
    Wipes and recreates the database schema ONCE for the entire test session.
    This ensures new columns (like custom_fields) are created.
    """
    with engine.connect() as connection:
        # 1. Enable Extensions
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        
        # 2. FIX: Drop dependent Views explicitly with CASCADE
        # This prevents "DependentObjectsStillExist" errors when dropping tables
        connection.execute(text("DROP VIEW IF EXISTS v_sentiment_mix CASCADE"))
        connection.execute(text("DROP VIEW IF EXISTS v_avg_response CASCADE"))
        
        connection.commit()

    # 3. Drop all tables to clear old schema
    Base.metadata.drop_all(bind=engine)
    
    # 4. Create all tables with new schema
    Base.metadata.create_all(bind=engine)
    
    yield
    
    # Optional: Cleanup after all tests are done
    # Base.metadata.drop_all(bind=engine)

# --- Database Session Fixture (Per Test) ---
@pytest.fixture(scope="function")
def db_session(setup_test_database):
    """
    Creates a new database session for a test.
    Rolls back the transaction at the end so tests don't affect each other.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session

    session.close()
    transaction.rollback()
    connection.close()

# --- Async Client Fixture ---
@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    """
    FastAPI Test Client with DB Override.
    """
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()

@pytest.fixture(autouse=True)
def mock_celery_tasks(monkeypatch):
    """
    Automatically mocks Celery task dispatch (.delay) for all tests.
    This prevents 'Connection to Redis lost' errors when running Pytest locally.
    """
    # 1. Mock Email Task
    mock_email = MagicMock()
    monkeypatch.setattr("app.tasks.email_tasks.send_email_task.delay", mock_email)
    
    # 2. Mock Bulk WhatsApp Task
    mock_bulk = MagicMock()
    monkeypatch.setattr("app.tasks.whatsapp_tasks.process_bulk_whatsapp_job.delay", mock_bulk)
    
    # 3. Mock AI Task
    mock_ai = MagicMock()
    monkeypatch.setattr("app.tasks.ai_tasks.process_message_ai.delay", mock_ai)
    
    return {
        "email": mock_email,
        "bulk": mock_bulk,
        "ai": mock_ai
    }