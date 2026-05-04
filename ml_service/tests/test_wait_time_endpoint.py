"""
test_wait_time_endpoint.py — Tests for the wait-time prediction endpoint.

All external dependencies (MLflow, DB) are mocked. No real services required.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient

# Patch mlflow before importing the app module
with patch("model_loader.mlflow"):
    import main
    from main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_payload(**overrides) -> dict:
    """Return a valid /predict/wait-time payload with optional overrides."""
    base = {
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
    base.update(overrides)
    return base


def _override_db():
    """Return a mock async DB session and a FastAPI dependency override."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()

    async def _fake_get_db():
        yield mock_session

    return mock_session, _fake_get_db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_predict_wait_time_returns_correct_schema():
    """Successful prediction returns the expected JSON schema and value."""
    mock_model = MagicMock()
    mock_model.predict = MagicMock(return_value=np.array([18.5]))

    _, fake_get_db = _override_db()

    from database import get_db

    app.dependency_overrides[get_db] = fake_get_db

    original_model = main.wait_time_model
    main.wait_time_model = mock_model

    try:
        with patch("main.get_current_model_version", return_value="3"):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/predict/wait-time", json=_make_payload()
                )

        assert response.status_code == 200
        data = response.json()
        assert "predicted_wait_minutes" in data
        assert "model_version" in data
        assert isinstance(data["predicted_wait_minutes"], float)
        assert isinstance(data["model_version"], str)
        assert data["predicted_wait_minutes"] == 18.5
        assert data["model_version"] == "3"
    finally:
        main.wait_time_model = original_model
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_predict_wait_time_negative_clipped_to_zero():
    """Negative predictions are clipped to 0.0."""
    mock_model = MagicMock()
    mock_model.predict = MagicMock(return_value=np.array([-5.0]))

    _, fake_get_db = _override_db()

    from database import get_db

    app.dependency_overrides[get_db] = fake_get_db

    original_model = main.wait_time_model
    main.wait_time_model = mock_model

    try:
        with patch("main.get_current_model_version", return_value="2"):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/predict/wait-time", json=_make_payload()
                )

        assert response.status_code == 200
        data = response.json()
        assert data["predicted_wait_minutes"] == 0.0
    finally:
        main.wait_time_model = original_model
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_predict_wait_time_model_not_loaded_returns_503():
    """When model is None, endpoint returns 503."""
    original_model = main.wait_time_model
    main.wait_time_model = None

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/predict/wait-time", json=_make_payload()
            )

        assert response.status_code == 503
        assert response.json()["detail"] == "Model not loaded yet"
    finally:
        main.wait_time_model = original_model


@pytest.mark.asyncio
async def test_health_returns_ok():
    """GET /health returns 200 with status=ok."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_health_shows_degraded_when_model_not_loaded():
    """Health still returns 200 even when no model is loaded, but
    models_loaded is False so monitoring dashboards can detect it."""
    original_flag = main.models_loaded
    main.models_loaded = False

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["models_loaded"] is False
    finally:
        main.models_loaded = original_flag


@pytest.mark.asyncio
async def test_reload_models_requires_secret_header():
    """POST /reload-models without the X-Internal-Secret header returns 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/reload-models")

    assert response.status_code == 401
