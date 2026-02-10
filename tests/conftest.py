import pytest
import pytest_asyncio
import uuid
import asyncio
from dotenv import load_dotenv
from unittest.mock import MagicMock
from datetime import timedelta

# 1. Force load .env
load_dotenv()

from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session

# Rename to avoid collision with 'app' module
from app.main import app as fastapi_app 
from app.database import Base, get_db
from app.core.config import settings

# Import Authentication Utils for fixtures
from app.authentication.hashing import hash_password
from app.authentication.router import create_access_token
from app.models import User

# --- Database Setup ---
if "sqlite" in settings.DATABASE_URL:
    print(f"WARNING: Tests are running against SQLite: {settings.DATABASE_URL}")
else:
    print(f"INFO: Tests are running against PostgreSQL: {settings.DATABASE_URL}")

# Pool size 1 is critical for tests to ensure all connections (if shared) lock correctly
engine = create_engine(settings.DATABASE_URL, pool_size=1, max_overflow=0)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """
    Recreates the schema once per test session.
    """
    with engine.connect() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        connection.execute(text("DROP VIEW IF EXISTS v_sentiment_mix CASCADE"))
        connection.execute(text("DROP VIEW IF EXISTS v_avg_response CASCADE"))
        connection.commit()

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    # Optional: cleanup after all tests
    # Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def db_session(setup_test_database):
    """
    Creates a fresh database session for a test.
    
    CRITICAL ARCHITECTURE CHANGE:
    Uses a Nested Transaction (SAVEPOINT). 
    This allows the Service Layer to call `db.commit()` (which commits the Savepoint)
    without committing the actual DB transaction that isolates the test.
    """
    connection = engine.connect()
    transaction = connection.begin() # The outer "Test" transaction
    
    # Bind session to the connection, not the engine
    session = TestingSessionLocal(bind=connection)

    # Start a nested transaction (Savepoint)
    nested = session.begin_nested()

    # If the app code calls session.commit, it will end the nested transaction.
    # We must intercept this and start a new nested transaction immediately 
    # so the session remains usable.
    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(session, transaction):
        if transaction.nested and not transaction._parent.nested:
            session.expire_all()
            session.begin_nested()

    yield session

    # Teardown
    session.close()
    transaction.rollback() # Rolls back everything, including what the Service "committed"
    connection.close()

@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    def override_get_db():
        yield db_session
    
    fastapi_app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test", timeout=10.0) as ac:
        yield ac
    
    fastapi_app.dependency_overrides.clear()

@pytest.fixture(scope="function", autouse=True)
def wire_event_loop(monkeypatch):
    try:
        import app.core.event_bus as bus_module
        loop = asyncio.get_running_loop()
        monkeypatch.setattr(bus_module, "_main_loop", loop)
    except RuntimeError:
        pass 

# --- Mocking Fixtures ---
@pytest.fixture(autouse=True)
def mock_celery_tasks(monkeypatch):
    mock_email = MagicMock()
    monkeypatch.setattr("app.tasks.email_tasks.send_email_task.delay", mock_email)
    
    mock_bulk = MagicMock()
    monkeypatch.setattr("app.tasks.whatsapp_tasks.process_bulk_whatsapp_job.delay", mock_bulk)
    
    mock_ai = MagicMock()
    monkeypatch.setattr("app.tasks.ai_tasks.process_message_ai.delay", mock_ai)
    return {"email": mock_email, "bulk": mock_bulk, "ai": mock_ai}

# --- AUTHENTICATION FIXTURES ---
@pytest.fixture(scope="function")
def test_user(db_session):
    password = "test_password"
    hashed = hash_password(password)
    # Use uuid to ensure uniqueness per test run
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    
    user = User(
        email=email,
        hashed_password=hashed,
        name="Test User",
        tenant_id=1,
        role_id=None
    )
    db_session.add(user)
    db_session.commit() # Commits to the Savepoint
    db_session.refresh(user)
    return user

@pytest.fixture(scope="function")
def auth_headers(test_user):
    access_token = create_access_token(
        data={"sub": test_user.email},
        expires_delta=timedelta(minutes=30)
    )
    return {"Authorization": f"Bearer {access_token}"}