import pytest
import respx
from httpx import Response
from unittest.mock import patch
from tasks.retrain_task import run_weekly_retraining, ML_SERVICE_URL

class TestRetrainingTask:

    @respx.mock
    @patch("tasks.retrain_task.INTERNAL_SECRET", "test_secret")
    @pytest.mark.asyncio
    async def test_run_weekly_retraining_success(self):
        """Task should return success when ML service returns 200."""
        # Mock the ML service /retrain endpoint
        respx.post(f"{ML_SERVICE_URL}/retrain").mock(
            return_value=Response(200, json={"status": "training_started", "job_id": "123"})
        )
        
        # This function doesn't return the JSON but logs it, 
        # so we check if the request was made correctly.
        await run_weekly_retraining()
        
        assert len(respx.calls) == 1
        assert respx.calls[0].request.headers["X-Internal-Secret"] == "test_secret"

    @respx.mock
    @patch("tasks.retrain_task.INTERNAL_SECRET", "test_secret")
    @pytest.mark.asyncio
    async def test_run_weekly_retraining_auth_failure(self):
        """Should handle 401 Unauthorized from ML service."""
        respx.post(f"{ML_SERVICE_URL}/retrain").mock(
            return_value=Response(401, json={"detail": "Unauthorized"})
        )
        
        await run_weekly_retraining()
        # It logs the error, doesn't raise
        assert len(respx.calls) == 1

    @respx.mock
    @patch("tasks.retrain_task.INTERNAL_SECRET", "test_secret")
    @pytest.mark.asyncio
    async def test_run_weekly_retraining_connection_error(self):
        """Should handle cases where the ML service is down."""
        respx.post(f"{ML_SERVICE_URL}/retrain").side_effect = Exception("Connection refused")
        
        await run_weekly_retraining()
        # Logs the exception
        assert len(respx.calls) == 1
