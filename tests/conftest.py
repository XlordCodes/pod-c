# tests/conftest.py
import pytest
import pytest_asyncio
from dotenv import load_dotenv

# 1. Force load .env
load_dotenv()

from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base, get_db
from app.core.config import settings

from app.models import User, BulkJob, BulkMessage, Contact, Conversation, ChatMessage
from app.models_vector import MessageEmbedding
from app.models_status import MessageStatus
from app.models_reply import ReplySuggestion

# --- Database Setup ---
if "sqlite" in settings.DATABASE_URL:
    print(f"WARNING: Tests are running against SQLite: {settings.DATABASE_URL}")
else:
    print(f"INFO: Tests are running against PostgreSQL: {settings.DATABASE_URL}")

engine = create_engine(settings.DATABASE_URL, pool_size=5, max_overflow=0)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- 2. Database Session Fixture ---
@pytest.fixture(scope="function")
def db_session():
    with engine.connect() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        connection.commit()

    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session

    session.close()
    transaction.rollback()
    connection.close()

# --- 3. Async Client Fixture ---
@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()