import sys
from pathlib import Path

# Add the backend directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from core.config import settings
os.environ["TEST_DATABASE_URL"] = settings.TEST_DATABASE_URL

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from main import app
from db.models import Base
from db.session import get_db
from core.config import settings

SQLALCHEMY_DATABASE_URL = settings.TEST_DATABASE_URL
ASYNC_SQLALCHEMY_DATABASE_URL = settings.ASYNC_TEST_DATABASE_URL

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

async_engine = create_async_engine(
    ASYNC_SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
AsyncTestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=async_engine, class_=AsyncSession
)

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

async def override_get_db():
    async with AsyncTestingSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="session")
def client():
    return TestClient(app)


@pytest.fixture
async def async_client():
    """Async HTTPX client against the FastAPI app for pre-production tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def mock_llm_router():
    """Controlled LLM router mock for tests that must not hit real providers."""
    from services.llm_router import LLM_Router

    mock = AsyncMock(spec=LLM_Router)
    mock.select_key.return_value = "test-key-123"
    mock.call.return_value = MagicMock(
        text="This is a test response.",
        finish_reason="stop",
        tool_call=None,
    )
    return mock


@pytest.fixture
async def seeded_db(db_session):
    """Seed a small clinic dataset for booking and admin tests."""
    from tests.factories import seed_clinic_data

    return await seed_clinic_data(db_session)


@pytest.fixture
def session_id():
    import uuid

    return f"test-{uuid.uuid4().hex[:8]}"
