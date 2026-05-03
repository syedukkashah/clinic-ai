"""
conftest.py — Shared fixtures for ml_service tests.

Builds on the existing fixtures and adds extras needed by
test_ml_models.py, test_feature_pipeline.py, and test_ml_service.py.

Existing fixtures (keep as-is — her code):
    async_client          — httpx client bound to FastAPI app
    mock_db_session       — mocked async DB session
    mock_model            — mock MLflow model returning [18.5]
    valid_wait_time_payload — valid POST /predict/wait-time body

Added fixtures:
    mock_load_model       — mock for patient load model (returns 13-hour array)
    valid_load_payload    — valid POST /predict/patient-load body
    sample_appointments_df — small synthetic DataFrame for ML tests
    production_model_rmse_mock — patches get_production_model_rmse
"""

import os

# ── Set INTERNAL_SECRET before importing main so auth checks work in tests ────
# Tests that expect 401 send no header or wrong header.
# Tests that expect 200 must send exactly this value.
os.environ.setdefault("INTERNAL_SECRET", "test-secret")

# ── Provide a dummy DATABASE_URL so database.py doesn't crash at import time ─
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/testdb"
)

from unittest.mock import AsyncMock, MagicMock, patch
import numpy as np
import pandas as pd
import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from httpx import ASGITransport, AsyncClient

# Patch mlflow BEFORE importing main — model_loader.py calls mlflow at import time
with patch("model_loader.mlflow"):
    from main import app

from database import get_db


# ── Existing fixtures (her code — do not modify) ──────────────────────────────

@pytest_asyncio.fixture
async def async_client(mock_db_session):
    """
    Async httpx client bound to the FastAPI app.
    DB dependency is overridden to avoid needing a real PostgreSQL connection.
    The override is torn down after each test.
    """
    async def fake_get_db():
        yield mock_db_session

    app.dependency_overrides[get_db] = fake_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def mock_db_session():
    """A mocked async DB session whose execute() and commit() are no-ops."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    # run_sync is used by predict_patient_load — return a mock DataFrame
    session.run_sync = AsyncMock(return_value=pd.DataFrame(
        [[0] * 8 for _ in range(13)],  # 13 hours × 8 columns placeholder
    ))
    return session


@pytest.fixture
def mock_model():
    """A mock MLflow PyFunc model whose predict() returns a configurable array."""
    model = MagicMock()
    model.predict = MagicMock(return_value=np.array([18.5]))
    # Allow metadata/signature access without crashing
    model.metadata = MagicMock()
    model.metadata.signature = None
    return model


@pytest.fixture
def valid_wait_time_payload() -> dict:
    """A valid request body for POST /predict/wait-time."""
    return {
        "slot_id":              42,
        "doctor_id":            7,
        "hour_of_day":          10,
        "day_of_week":          1,
        "queue_depth":          3,
        "booking_lead_days":    2,
        "is_follow_up":         False,
        "appointments_before":  1,
        "avg_consult_duration": 15.0,
        "appointment_id":       100,
    }


# ── Additional fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def mock_load_model():
    """
    Mock for patient_load_model.
    Returns a 13-element array covering hours 8–20.
    """
    model = MagicMock()
    model.predict = MagicMock(
        return_value=np.array([3, 4, 7, 8, 6, 5, 4, 3, 4, 5, 6, 5, 4])
    )
    return model


@pytest.fixture
def valid_load_payload() -> dict:
    """A valid request body for POST /predict/patient-load."""
    # Use a future date so the endpoint doesn't reject it as past
    future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    return {
        "doctor_id": 1,
        "date":      future_date,
        "specialty": "general",
    }


@pytest.fixture
def sample_appointments_df() -> pd.DataFrame:
    """
    Small synthetic appointments DataFrame that matches the real CSV schema.
    Used by ML model unit tests — no file I/O needed.
    500 rows, ~92% show-up rate, all required columns present.
    Data has deliberate structure (queue_depth drives wait time) so
    ML models can beat the mean baseline.
    """
    np.random.seed(42)
    n = 500
    start = datetime(2024, 1, 1)
    records = []
    for i in range(n):
        doctor_id    = int(np.random.randint(1, 12))
        hour         = int(np.random.randint(8, 20))
        queue        = int(np.random.randint(0, 10))
        consult_dur  = round(float(np.random.uniform(8, 20)), 1)
        showed       = bool(np.random.binomial(1, 0.92))
        # Structured wait: longer queue + slow doctor = longer wait
        wait = max(0.0, queue * 5.0 + consult_dur * 0.5 + np.random.normal(0, 3)) if showed else None

        records.append({
            "patient_id":             int(np.random.randint(1, 500)),
            "patient_age":            int(np.random.randint(18, 80)),
            "patient_preferred_lang": np.random.choice(["en", "ur"]),
            "doctor_id":              doctor_id,
            "specialty":              np.random.choice(["general", "cardiology",
                                                         "pediatrics", "orthopedics",
                                                         "dermatology"]),
            "day_of_week":            int(np.random.randint(0, 7)),
            "hour_of_day":            hour,
            "booking_lead_days":      int(np.random.randint(0, 30)),
            "appointments_before":    int(np.random.randint(0, 8)),
            "queue_depth":            queue,
            "avg_consult_duration":   consult_dur,
            "historical_wait_slot":   round(float(np.random.uniform(2, 30)), 2),
            "is_follow_up":           bool(np.random.binomial(1, 0.3)),
            "is_holiday":             False,
            "is_ramadan":             False,
            "is_day_after_holiday":   False,
            "urgency":                np.random.choice(["routine", "moderate", "urgent"]),
            "season":                 np.random.choice(["flu_season", "normal", "heat_season"]),
            "booking_channel":        np.random.choice(["chat", "voice_note",
                                                         "webrtc_call", "twilio_call"]),
            "week_of_year":           int(np.random.randint(1, 53)),
            "showed_up":              showed,
            "actual_wait_minutes":    round(wait, 2) if wait is not None else None,
            "scheduled_at":           (start + timedelta(
                                           days=i // 5,
                                           hours=hour,
                                       )).isoformat(),
            "scheduled_date":         (start + timedelta(days=i // 5)).strftime("%Y-%m-%d"),
        })
    return pd.DataFrame(records)


@pytest.fixture
def db_override(mock_db_session):
    """
    Returns a FastAPI dependency override function for get_db.
    Use this to inject mock_db_session into endpoints during testing.

    Usage:
        from database import get_db
        app.dependency_overrides[get_db] = db_override
        # ... test ...
        app.dependency_overrides.pop(get_db, None)
    """
    async def _fake_get_db():
        yield mock_db_session
    return _fake_get_db


@pytest.fixture
def patched_model_version():
    """
    Context manager fixture that patches get_current_model_version.
    Usage: with patched_model_version("3"): ...
    """
    def _patch(version: str = "1"):
        return patch("main.get_current_model_version", return_value=version)
    return _patch


@pytest.fixture
def valid_secret_headers() -> dict:
    """
    Headers containing the correct INTERNAL_SECRET for /reload-models tests.
    Matches the value set at the top of this conftest.
    """
    return {"X-Internal-Secret": os.environ["INTERNAL_SECRET"]}