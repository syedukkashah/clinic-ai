"""
test_ml_service.py — Integration tests for both ML service endpoints.

Tests:
  POST /predict/wait-time    — ML Model 1
  POST /predict/patient-load — ML Model 2
  GET  /health
  POST /reload-models

Uses conftest.py fixtures (async_client, mock_model, valid_wait_time_payload).
All MLflow and DB dependencies are mocked — no real services needed.

Spec reference: Section 24 API contracts, Section 21 M3 test ownership
Run from ml_service/:
    pytest tests/test_ml_service.py -v
"""

import numpy as np
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

# Future date used by all patient-load tests (past dates return 400)
FUTURE_DATE = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")


# ── Wait-time endpoint tests ───────────────────────────────────────────────────

class TestWaitTimeEndpoint:

    @pytest.mark.asyncio
    async def test_returns_correct_schema(self, async_client, mock_model, valid_wait_time_payload):
        """
        Spec Section 24:
        Response must contain predicted_wait_minutes (float) and model_version (str).
        """
        import main
        original = main.wait_time_model
        main.wait_time_model = mock_model

        try:
            with patch("main.get_current_model_version", return_value="3"):
                response = await async_client.post(
                    "/predict/wait-time", json=valid_wait_time_payload
                )
            assert response.status_code == 200
            data = response.json()
            assert "predicted_wait_minutes" in data, "Missing predicted_wait_minutes"
            assert "model_version" in data,          "Missing model_version"
            assert isinstance(data["predicted_wait_minutes"], float)
            assert isinstance(data["model_version"], str)
        finally:
            main.wait_time_model = original

    @pytest.mark.asyncio
    async def test_predicted_value_matches_mock(self, async_client, valid_wait_time_payload):
        """The value returned must match what the model's predict() returns."""
        import main
        mock = MagicMock()
        mock.predict = MagicMock(return_value=np.array([22.7]))
        mock.metadata = MagicMock()
        mock.metadata.signature = None
        original = main.wait_time_model
        main.wait_time_model = mock

        try:
            with patch("main.get_current_model_version", return_value="1"):
                response = await async_client.post(
                    "/predict/wait-time", json=valid_wait_time_payload
                )
            assert response.status_code == 200
            assert response.json()["predicted_wait_minutes"] == 22.7
        finally:
            main.wait_time_model = original

    @pytest.mark.asyncio
    async def test_negative_prediction_clipped_to_zero(self, async_client, valid_wait_time_payload):
        """
        Model may return negative values — endpoint must clip to 0.0.
        Spec: predictions.clip(0)
        """
        import main
        mock = MagicMock()
        mock.predict = MagicMock(return_value=np.array([-9.3]))
        mock.metadata = MagicMock()
        mock.metadata.signature = None
        original = main.wait_time_model
        main.wait_time_model = mock

        try:
            with patch("main.get_current_model_version", return_value="1"):
                response = await async_client.post(
                    "/predict/wait-time", json=valid_wait_time_payload
                )
            assert response.status_code == 200
            assert response.json()["predicted_wait_minutes"] == 0.0
        finally:
            main.wait_time_model = original

    @pytest.mark.asyncio
    async def test_model_not_loaded_returns_503(self, async_client, valid_wait_time_payload):
        """
        Spec: model is loaded at startup. If not loaded, return 503 not 500.
        Agents depend on this — 503 means retry, 500 means bug.
        """
        import main
        original = main.wait_time_model
        main.wait_time_model = None

        try:
            response = await async_client.post(
                "/predict/wait-time", json=valid_wait_time_payload
            )
            assert response.status_code == 503
            assert "detail" in response.json()
        finally:
            main.wait_time_model = original

    @pytest.mark.asyncio
    async def test_missing_required_field_returns_422(self, async_client):
        """Pydantic validation — missing required field must return 422."""
        response = await async_client.post(
            "/predict/wait-time",
            json={"doctor_id": 1}  # missing most required fields
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_field_type_returns_422(self, async_client, valid_wait_time_payload):
        """Pydantic validation — wrong type for numeric field must return 422."""
        payload = valid_wait_time_payload.copy()
        payload["hour_of_day"] = "morning"  # must be int
        response = await async_client.post("/predict/wait-time", json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_hour_of_day_below_8_returns_422(self, async_client, valid_wait_time_payload):
        """
        Spec schema: hour_of_day must be 8–20.
        Booking slots don't exist before 8am.
        """
        payload = valid_wait_time_payload.copy()
        payload["hour_of_day"] = 7  # below minimum
        response = await async_client.post("/predict/wait-time", json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_hour_of_day_above_20_returns_422(self, async_client, valid_wait_time_payload):
        """Spec schema: hour_of_day must be 8–20. Clinic closes at 8pm."""
        payload = valid_wait_time_payload.copy()
        payload["hour_of_day"] = 21  # above maximum
        response = await async_client.post("/predict/wait-time", json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_logs_prediction_to_db(self, async_client, mock_model,
                                          valid_wait_time_payload, mock_db_session):
        """
        Spec Section 18: every ML call must log to ml_predictions table.
        Verify DB execute() is called at least once during prediction.
        """
        import main
        original = main.wait_time_model
        main.wait_time_model = mock_model

        try:
            with patch("main.get_current_model_version", return_value="1"):
                response = await async_client.post(
                    "/predict/wait-time", json=valid_wait_time_payload
                )
            assert response.status_code == 200
            # DB must have been touched for prediction logging
            assert mock_db_session.execute.called or mock_db_session.commit.called
        finally:
            main.wait_time_model = original

    @pytest.mark.asyncio
    async def test_model_version_included_in_response(self, async_client, valid_wait_time_payload):
        """
        Spec Section 18: response must include model_version so
        ml_predictions table can track which model made each prediction.
        """
        import main
        mock = MagicMock()
        mock.predict = MagicMock(return_value=np.array([10.0]))
        mock.metadata = MagicMock()
        mock.metadata.signature = None
        original = main.wait_time_model
        main.wait_time_model = mock

        try:
            with patch("main.get_current_model_version", return_value="5"):
                response = await async_client.post(
                    "/predict/wait-time", json=valid_wait_time_payload
                )
            assert response.status_code == 200
            assert response.json()["model_version"] == "5"
        finally:
            main.wait_time_model = original


# ── Patient load endpoint tests ────────────────────────────────────────────────

class TestPatientLoadEndpoint:

    def _make_load_mock(self, values=None):
        """Helper — build a patient_load_model mock with controlled predict output."""
        if values is None:
            values = np.array([3, 4, 7, 8, 6, 5, 4, 3, 4, 5, 6, 5, 4])
        mock = MagicMock()
        mock.predict = MagicMock(return_value=np.array(values))
        return mock

    @pytest.mark.asyncio
    async def test_returns_correct_schema(self, async_client):
        """
        Spec Section 24:
        Response must contain forecast (dict), peak_hour (int), peak_hour_patients (int).
        """
        import main
        original = main.patient_load_model
        main.patient_load_model = self._make_load_mock()

        try:
            with patch("main.get_current_model_version", return_value="1"), \
                 patch("main.trained_columns", []):
                response = await async_client.post(
                    "/predict/patient-load",
                    json={"doctor_id": 1, "date": FUTURE_DATE, "specialty": "general"}
                )
            assert response.status_code == 200
            data = response.json()
            assert "forecast" in data
            assert "peak_hour" in data
            assert "peak_hour_patients" in data
            assert isinstance(data["forecast"], dict)
            assert isinstance(data["peak_hour"], int)
            assert isinstance(data["peak_hour_patients"], int)
        finally:
            main.patient_load_model = original

    @pytest.mark.asyncio
    async def test_forecast_covers_all_hours_8_to_20(self, async_client):
        """
        Spec Section 15: forecast must cover hours 8–20 (13 hours).
        Scheduling Agent iterates over all hours to detect peak load.
        """
        import main
        original = main.patient_load_model
        main.patient_load_model = self._make_load_mock()

        try:
            with patch("main.get_current_model_version", return_value="1"), \
                 patch("main.trained_columns", []):
                response = await async_client.post(
                    "/predict/patient-load",
                    json={"doctor_id": 1, "date": FUTURE_DATE, "specialty": "general"}
                )
            assert response.status_code == 200
            forecast = response.json()["forecast"]
            assert len(forecast) == 13, f"Expected 13 hours, got {len(forecast)}"
            for h in range(8, 21):
                assert str(h) in forecast, f"Hour {h} missing from forecast"
                assert forecast[str(h)] >= 0
        finally:
            main.patient_load_model = original

    @pytest.mark.asyncio
    async def test_peak_hour_within_valid_range(self, async_client):
        """
        peak_hour must be between 8 and 20 inclusive.
        Scheduling Agent uses this to pre-open slots before the surge.
        """
        import main
        original = main.patient_load_model
        # Peak is at index 2 → hour 10 (highest value = 9)
        main.patient_load_model = self._make_load_mock(
            [2, 3, 9, 8, 6, 5, 4, 3, 4, 5, 6, 5, 4]
        )

        try:
            with patch("main.get_current_model_version", return_value="1"), \
                 patch("main.trained_columns", []):
                response = await async_client.post(
                    "/predict/patient-load",
                    json={"doctor_id": 1, "date": FUTURE_DATE, "specialty": "general"}
                )
            assert response.status_code == 200
            peak = response.json()["peak_hour"]
            assert 8 <= peak <= 20, f"peak_hour {peak} outside valid range 8–20"
        finally:
            main.patient_load_model = original

    @pytest.mark.asyncio
    async def test_peak_hour_matches_highest_forecast_value(self, async_client):
        """
        peak_hour must correspond to the hour with the highest predicted count.
        Spec Section 15: peak_hour is used by Scheduling Agent for redistribution.
        """
        import main
        original = main.patient_load_model
        # Hour 11 (index 3) has value 12 — the clear peak
        main.patient_load_model = self._make_load_mock(
            [2, 3, 5, 12, 6, 5, 4, 3, 4, 5, 6, 5, 4]
        )

        try:
            with patch("main.get_current_model_version", return_value="1"), \
                 patch("main.trained_columns", []):
                response = await async_client.post(
                    "/predict/patient-load",
                    json={"doctor_id": 1, "date": FUTURE_DATE, "specialty": "general"}
                )
            assert response.status_code == 200
            data = response.json()
            assert data["peak_hour"] == 11
            assert data["peak_hour_patients"] == 12
        finally:
            main.patient_load_model = original

    @pytest.mark.asyncio
    async def test_past_date_returns_400(self, async_client):
        """
        Spec: past dates must return 400 — can't forecast the past.
        Scheduling Agent only requests future dates — this guards against bugs.
        """
        import main
        original = main.patient_load_model
        main.patient_load_model = self._make_load_mock()

        try:
            response = await async_client.post(
                "/predict/patient-load",
                json={"doctor_id": 1, "date": "2020-01-01", "specialty": "general"}
            )
            assert response.status_code == 400
            assert "detail" in response.json()
        finally:
            main.patient_load_model = original

    @pytest.mark.asyncio
    async def test_model_not_loaded_returns_503(self, async_client):
        """
        When patient_load_model is None, endpoint must return 503.
        503 = service unavailable (model loading), not 500 (bug).
        """
        import main
        original = main.patient_load_model
        main.patient_load_model = None

        try:
            response = await async_client.post(
                "/predict/patient-load",
                json={"doctor_id": 1, "date": FUTURE_DATE, "specialty": "general"}
            )
            assert response.status_code == 503
            assert "detail" in response.json()
        finally:
            main.patient_load_model = original

    @pytest.mark.asyncio
    async def test_all_forecast_values_non_negative(self, async_client):
        """
        Negative patient counts are nonsensical — all values must be >= 0.
        Spec: predictions.clip(0) must be applied before returning.
        """
        import main
        original = main.patient_load_model
        # -1 at hour 8 must be clipped to 0
        main.patient_load_model = self._make_load_mock(
            [-1, 4, 7, 8, 6, 5, 4, 3, 4, 5, 6, 5, 4]
        )

        try:
            with patch("main.get_current_model_version", return_value="1"), \
                 patch("main.trained_columns", []):
                response = await async_client.post(
                    "/predict/patient-load",
                    json={"doctor_id": 1, "date": FUTURE_DATE, "specialty": "general"}
                )
            # If endpoint returns 200, verify clipping; 500 means clip failed
            assert response.status_code == 200, \
                f"Expected 200, got {response.status_code}: {response.text}"
            forecast = response.json()["forecast"]
            for h, v in forecast.items():
                assert v >= 0, f"Hour {h} has negative count {v} — clip(0) not applied"
        finally:
            main.patient_load_model = original

    @pytest.mark.asyncio
    async def test_missing_doctor_id_returns_422(self, async_client):
        """Pydantic validation — doctor_id is required."""
        response = await async_client.post(
            "/predict/patient-load",
            json={"date": FUTURE_DATE, "specialty": "general"}
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_date_returns_422(self, async_client):
        """Pydantic validation — date is required."""
        response = await async_client.post(
            "/predict/patient-load",
            json={"doctor_id": 1, "specialty": "general"}
        )
        assert response.status_code == 422


# ── Health endpoint tests ──────────────────────────────────────────────────────

class TestHealthEndpoint:

    @pytest.mark.asyncio
    async def test_health_returns_200(self, async_client):
        """GET /health must always return 200 — used by CI/CD health check gate."""
        response = await async_client.get("/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_has_status_field(self, async_client):
        """Health response must contain a 'status' field with value 'ok'."""
        response = await async_client.get("/health")
        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_health_shows_models_loaded_flag(self, async_client):
        """
        Health must expose models_loaded so Grafana Dashboard 3 can
        show model availability without querying MLflow.
        """
        response = await async_client.get("/health")
        data = response.json()
        assert "models_loaded" in data
        assert isinstance(data["models_loaded"], bool)

    @pytest.mark.asyncio
    async def test_health_degraded_when_no_model(self, async_client):
        """
        When models_loaded is False, health still returns 200 but flag is False.
        Spec: 'always returns 200 so CI/CD probes don't fail while MLflow is booting'.
        """
        import main
        original = main.models_loaded
        main.models_loaded = False

        try:
            response = await async_client.get("/health")
            assert response.status_code == 200
            assert response.json()["models_loaded"] is False
        finally:
            main.models_loaded = original

    @pytest.mark.asyncio
    async def test_metrics_endpoint_exists(self, async_client):
        """
        Spec Section 26: /metrics endpoint must exist for Prometheus scraping.
        Grafana Dashboard 1 (system health) depends on this.
        """
        response = await async_client.get("/metrics")
        assert response.status_code == 200


# ── Reload endpoint tests ──────────────────────────────────────────────────────

class TestReloadEndpoint:

    @pytest.mark.asyncio
    async def test_reload_requires_auth_header(self, async_client):
        """
        POST /reload-models without X-Internal-Secret must return 401.
        Celery retraining task sends this header — external callers must not
        be able to trigger a hot-reload.
        """
        response = await async_client.post("/reload-models")
        assert response.status_code == 401, (
            f"Expected 401 when no secret sent, got {response.status_code}. "
            "Check that INTERNAL_SECRET env var is set and auth check is not skipped."
        )

    @pytest.mark.asyncio
    async def test_reload_with_wrong_secret_returns_401(self, async_client):
        """Wrong secret key must also return 401."""
        response = await async_client.post(
            "/reload-models",
            headers={"X-Internal-Secret": "wrong_secret_completely"}
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_reload_with_correct_secret_returns_200(self, async_client,
                                                           valid_secret_headers):
        """
        Correct secret must allow the reload through.
        Called by M6 Celery pipeline after model promotion.
        """
        with patch("main.load_production_model", return_value=MagicMock()), \
             patch("main.get_current_model_version", return_value="2"):
            response = await async_client.post(
                "/reload-models", headers=valid_secret_headers
            )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_reload_response_schema(self, async_client, valid_secret_headers):
        """
        Reload response must contain 'reloaded' (list) and 'status' (str).
        Celery task checks these fields to confirm success.
        """
        with patch("main.load_production_model", return_value=MagicMock()), \
             patch("main.get_current_model_version", return_value="2"):
            response = await async_client.post(
                "/reload-models", headers=valid_secret_headers
            )
        assert response.status_code == 200
        data = response.json()
        assert "reloaded" in data
        assert "status" in data
        assert isinstance(data["reloaded"], list)
        assert len(data["reloaded"]) == 2  # both models

    @pytest.mark.asyncio
    async def test_reload_lists_both_models(self, async_client, valid_secret_headers):
        """
        Spec Section 25: both wait_time_model and patient_load_model must be reloaded.
        M6 retraining pipeline promotes both models — both must hot-reload.
        """
        with patch("main.load_production_model", return_value=MagicMock()), \
             patch("main.get_current_model_version", return_value="2"):
            response = await async_client.post(
                "/reload-models", headers=valid_secret_headers
            )
        reloaded = response.json()["reloaded"]
        assert "wait_time_model" in reloaded
        assert "patient_load_model" in reloaded