"""
conftest.py — Shared fixtures for ml_service tests.

Provides an async httpx client wired to the FastAPI app with mocked
DB and model dependencies.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# We need to patch mlflow BEFORE importing main, because model_loader.py
# calls mlflow.set_tracking_uri() at import time.
with patch("model_loader.mlflow"):
    from main import app


@pytest_asyncio.fixture
async def async_client():
    """Async httpx client bound to the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_db_session():
    """A mocked async DB session whose execute() and commit() are no-ops."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def mock_model():
    """A mock MLflow PyFunc model whose predict() returns a configurable array."""
    model = MagicMock()
    model.predict = MagicMock(return_value=np.array([18.5]))
    return model


@pytest.fixture
def valid_wait_time_payload() -> dict:
    """A valid request body for POST /predict/wait-time."""
    return {
        "slot_id": 42,
        "doctor_id": 7,
        "hour_of_day": 10,
        "day_of_week": 1,
        "queue_depth": 3,
        "booking_lead_days": 2,
        "is_follow_up": False,
        "appointments_before": 1,
        "avg_consult_duration": 15.0,
        "appointment_id": 100,
    }
