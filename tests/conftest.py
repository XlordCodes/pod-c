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
    A wrapper around the standard SQLAlchemy Session.
    It intercepts commit() and rollback() to ensure they only work 
    on SAVEPOINTS, protecting the outer test transaction.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Start the first savepoint immediately
        self.begin_nested()

    def commit(self):
        """
        Mock Commit: Flush changes to DB (so queries see them),
        then restart the savepoint to 'seal' this step.
        """
        self.flush()
        self.expire_all()
        # Close current savepoint and start a new one
        super().commit() 
        self.begin_nested()

    def rollback(self):
        """
        Mock Rollback: Roll back ONLY the current savepoint (the failed step),
        then restart a new savepoint for the next step.
        Does NOT roll back the parent transaction (Test Setup).
        """
        super().rollback()
        self.begin_nested()

@pytest.fixture(scope="function")
def db_session(setup_test_database):
    """
    Creates a fresh database session for a test using the TestSession wrapper.
    """
    connection = engine.connect()
    transaction = connection.begin()
    
    # Use our custom class that handles nested transactions automatically
    session = TestSession(bind=connection)

    yield session

    # Teardown
    session.close()
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