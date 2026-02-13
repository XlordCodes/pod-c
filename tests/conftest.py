import pytest
import pytest_asyncio
import uuid
import asyncio
import os
from dotenv import load_dotenv
from unittest.mock import MagicMock
from datetime import timedelta

# 1. Force load .env
load_dotenv()

# 2. Override Redis configuration for local testing BEFORE importing app modules
# This prevents connection errors when running tests on Windows (where Redis hostname "redis" doesn't resolve)
os.environ["REDIS_HOST"] = "localhost"
os.environ["CELERY_BROKER_URL"] = "redis://localhost:6379/0"
os.environ["CELERY_RESULT_BACKEND"] = "redis://localhost:6379/0"

from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine, text
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

# Pool size 1 is critical for tests
engine = create_engine(settings.DATABASE_URL, pool_size=1, max_overflow=0)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def override_redis_config():
    """
    Override Redis configuration for local testing.
    
    Problem: Docker Compose uses hostname "redis", but on Windows localhost,
    this hostname doesn't resolve, causing connection errors (Error 11001).
    
    Solution: Force Redis to use "localhost" for tests since port 6379 is exposed.
    This runs at module import time (via os.environ above) and this fixture
    confirms the override was applied.
    """
    print(f"INFO: Redis configuration overridden for tests - Host: {settings.REDIS_HOST}, Port: {settings.REDIS_PORT}")
    print(f"INFO: Celery Broker: {settings.CELERY_BROKER_URL}")
    yield

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    with engine.connect() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        connection.execute(text("DROP VIEW IF EXISTS v_sentiment_mix CASCADE"))
        connection.execute(text("DROP VIEW IF EXISTS v_avg_response CASCADE"))
        connection.commit()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield

class TestSession(Session):
    """
    A wrapper around the standard SQLAlchemy Session that uses nested transactions (savepoints)
    to isolate service-level commits and rollbacks from the outer test transaction.
    
    Key Strategy:
    - The outer transaction (managed by the fixture) wraps the entire test
    - Each service commit/rollback operates on a SAVEPOINT, not the outer transaction
    - This allows services to use explicit transaction control without affecting test isolation
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._savepoint = None

    def commit(self):
        """
        Intercepts commit() to work on savepoints instead of the outer transaction.
        
        Flow:
        1. Flush changes to make them visible within the transaction
        2. Commit the current savepoint (makes changes durable within the outer transaction)
        3. Start a new savepoint for the next operation
        """
        # Flush to ensure all pending changes are written
        self.flush()
        
        # If we have an active savepoint, commit it
        if self._savepoint is not None:
            self._savepoint.commit()
            self._savepoint = None
        
        # Expire all objects to force fresh reads
        self.expire_all()
        
        # Start a new savepoint for the next operation
        self._savepoint = self.begin_nested()

    def rollback(self):
        """
        Intercepts rollback() to only rollback the current savepoint.
        
        Flow:
        1. Rollback the current savepoint (undoes changes since last savepoint)
        2. Start a new savepoint for the next operation
        
        CRITICAL: This does NOT rollback the outer transaction, preserving test setup data.
        """
        # If we have an active savepoint, rollback to it
        if self._savepoint is not None:
            self._savepoint.rollback()
            self._savepoint = None
        
        # Start a new savepoint for the next operation
        self._savepoint = self.begin_nested()

    def close(self):
        """
        Clean up savepoint state before closing.
        """
        if self._savepoint is not None:
            self._savepoint = None
        super().close()

@pytest.fixture(scope="function")
def db_session(setup_test_database):
    """
    Creates a fresh database session for a test using the TestSession wrapper.
    
    Architecture:
    1. Opens a connection to the database
    2. Starts an outer transaction (this wraps the entire test)
    3. Creates a TestSession bound to this connection
    4. The TestSession automatically manages savepoints for service-level transactions
    5. After the test, rolls back the outer transaction (cleanup)
    """
    connection = engine.connect()
    transaction = connection.begin()
    
    # Use our custom TestSession class
    session = TestSession(bind=connection)
    
    # Initialize the first savepoint
    session._savepoint = session.begin_nested()

    yield session

    # Teardown: Close session and rollback the outer transaction
    session.close()
    if transaction.is_active:
        transaction.rollback()
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

@pytest.fixture(autouse=True)
def mock_celery_tasks(monkeypatch):
    mock_email = MagicMock()
    monkeypatch.setattr("app.tasks.email_tasks.send_email_task.delay", mock_email)
    
    mock_bulk = MagicMock()
    monkeypatch.setattr("app.tasks.whatsapp_tasks.process_bulk_whatsapp_job.delay", mock_bulk)
    
    mock_ai = MagicMock()
    monkeypatch.setattr("app.tasks.ai_tasks.process_message_ai.delay", mock_ai)
    return {"email": mock_email, "bulk": mock_bulk, "ai": mock_ai}

@pytest.fixture(scope="function")
def test_user(db_session):
    password = "test_password"
    hashed = hash_password(password)
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    
    user = User(email=email, hashed_password=hashed, name="Test User", tenant_id=1, role_id=None)
    db_session.add(user)
    db_session.commit() 
    db_session.refresh(user)
    return user

@pytest.fixture(scope="function")
def auth_headers(test_user):
    access_token = create_access_token(data={"sub": test_user.email}, expires_delta=timedelta(minutes=30))
    return {"Authorization": f"Bearer {access_token}"}
