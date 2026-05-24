from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from tasks.retrain_task import ML_SERVICE_URL, run_weekly_retraining


def _mock_async_client(handler):
    real_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        return real_client(transport=httpx.MockTransport(handler))

    return factory


class TestRetrainingTask:
    @patch("tasks.retrain_task.INTERNAL_SECRET", "test_secret")
    @pytest.mark.asyncio
    async def test_run_weekly_retraining_success(self):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json={"status": "training_started", "job_id": "123"})

        with patch("tasks.retrain_task.httpx.AsyncClient", _mock_async_client(handler)):
            await run_weekly_retraining()

        assert len(requests) == 1
        assert str(requests[0].url) == f"{ML_SERVICE_URL}/retrain"
        assert requests[0].headers["X-Internal-Secret"] == "test_secret"

    @patch("tasks.retrain_task.INTERNAL_SECRET", "test_secret")
    @pytest.mark.asyncio
    async def test_run_weekly_retraining_auth_failure(self):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(401, json={"detail": "Unauthorized"})

        with patch("tasks.retrain_task.httpx.AsyncClient", _mock_async_client(handler)):
            await run_weekly_retraining()

        assert len(requests) == 1

    @patch("tasks.retrain_task.INTERNAL_SECRET", "test_secret")
    @pytest.mark.asyncio
    async def test_run_weekly_retraining_connection_error(self):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            raise httpx.ConnectError("Connection refused", request=request)

        with patch("tasks.retrain_task.httpx.AsyncClient", _mock_async_client(handler)):
            await run_weekly_retraining()

        assert len(requests) == 1
