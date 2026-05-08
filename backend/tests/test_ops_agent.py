"""
backend/tests/test_ops_agent.py

Tests for the Ops Monitor Agent.
Owner: Ibrahim (per the handoff — booking/orchestrator tests),
       but ops agent test ownership falls to M2 (per the SRS matrix).
       Ibrahim writes these as part of the initial implementation to unblock M2.

Run:
  pytest tests/test_ops_agent.py -v

All tests mock:
  - llm_router.call  (no real LLM keys needed)
  - DB session / crud  (no live Postgres needed)
  - Prometheus HTTP  (no live Prometheus needed)
  - joblib.load  (no trained anomaly model needed)

This matches the pattern of test_booking_agent.py.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.ops_agent import (
    OpsMonitorAgent,
    _dispatch_tool,
    score_anomaly,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def agent():
    return OpsMonitorAgent()


@pytest.fixture
def mock_db():
    db = AsyncMock()
    return db


def make_llm_response(content: str):
    """Build a mock LLM response object matching llm_router.call() return shape."""
    resp = MagicMock()
    resp.text = content
    resp.finish_reason = "stop"
    return resp


def tool_call_json(tool: str, args: Dict) -> str:
    return json.dumps({"tool": tool, "args": args})


# ---------------------------------------------------------------------------
# _parse_tool_call
# ---------------------------------------------------------------------------

class TestParseToolCall:
    def test_parses_bare_json(self, agent):
        raw = '{"tool": "get_ops_summary", "args": {"window_hours": 24}}'
        result = agent._parse_tool_call(raw)
        assert result == {"tool": "get_ops_summary", "args": {"window_hours": 24}}

    def test_parses_json_code_block(self, agent):
        raw = '```json\n{"tool": "score_anomaly", "args": {"booking_vector": [3,4,5]}}\n```'
        result = agent._parse_tool_call(raw)
        assert result is not None
        assert result["tool"] == "score_anomaly"

    def test_parses_embedded_json(self, agent):
        raw = "I will call this tool: {\"tool\": \"query_prometheus\", \"args\": {\"metric\": \"x\", \"window_min\": 10}}"
        result = agent._parse_tool_call(raw)
        assert result is not None
        assert result["tool"] == "query_prometheus"

    def test_returns_none_for_conclude(self, agent):
        raw = "CONCLUDE → Everything looks healthy. No anomalies detected."
        result = agent._parse_tool_call(raw)
        assert result is None

    def test_returns_none_for_plain_text(self, agent):
        result = agent._parse_tool_call("The system is operating normally.")
        assert result is None


# ---------------------------------------------------------------------------
# _build_trigger_message
# ---------------------------------------------------------------------------

class TestBuildTriggerMessage:
    def test_scheduled_trigger(self, agent):
        msg = agent._build_trigger_message("scheduled", {})
        assert "get_ops_summary" in msg
        assert "Routine" in msg

    def test_prometheus_webhook_trigger(self, agent):
        ctx = {"alertname": "HighBookingVolume", "value": "28.5"}
        msg = agent._build_trigger_message("prometheus_webhook", ctx)
        assert "HighBookingVolume" in msg
        assert "28.5" in msg

    def test_scheduling_overload_trigger(self, agent):
        ctx = {"doctor_id": 4, "severity": "warning", "message": "Wait exceeded"}
        msg = agent._build_trigger_message("scheduling_overload", ctx)
        assert "doctor_id=4" in msg

    def test_mlflow_drift_trigger(self, agent):
        ctx = {"model_name": "wait_time_model", "kl_divergence": 0.15}
        msg = agent._build_trigger_message("mlflow_drift", ctx)
        assert "wait_time_model" in msg
        assert "0.15" in msg

    def test_unknown_trigger_fallback(self, agent):
        msg = agent._build_trigger_message("weird_trigger", {})
        assert "get_ops_summary" in msg


# ---------------------------------------------------------------------------
# score_anomaly (pure function — no mocking needed)
# ---------------------------------------------------------------------------

class TestScoreAnomaly:
    @patch("agents.ops_agent.joblib.load")
    def test_returns_float(self, mock_load):
        mock_model = MagicMock()
        mock_model.decision_function.return_value = [-0.5]
        mock_model.n_features_in_ = 6
        mock_load.return_value = mock_model

        result = score_anomaly([3, 4, 3, 18, 22, 31])
        assert isinstance(result, float)
        assert result == -0.5

    @patch("agents.ops_agent.joblib.load")
    def test_neutral_score_on_empty_vector(self, mock_load):
        result = score_anomaly([])
        assert result == 0.0
        mock_load.assert_not_called()

    @patch("agents.ops_agent.joblib.load", side_effect=FileNotFoundError)
    def test_graceful_on_missing_model(self, _):
        result = score_anomaly([3, 4, 5, 6])
        assert result == 0.0

    @patch("agents.ops_agent.joblib.load")
    def test_pads_short_vector(self, mock_load):
        mock_model = MagicMock()
        mock_model.decision_function.return_value = [-0.2]
        mock_model.n_features_in_ = 10
        # First call raises ValueError (shape mismatch), second succeeds
        mock_model.decision_function.side_effect = [
            ValueError("shape mismatch"),
            [-0.2],
        ]
        mock_load.return_value = mock_model

        result = score_anomaly([1, 2, 3])
        assert result == -0.2


class TestCheckCeleryHealth:

    @pytest.mark.asyncio
    @patch("tasks.celery_app.celery_app")
    async def test_all_workers_up(self, mock_celery):
        mock_inspector = MagicMock()
        mock_inspector.ping.return_value = {"celery@worker1": {"ok": "pong"}}
        mock_inspector.active.return_value = {"celery@worker1": []}
        mock_celery.control.inspect.return_value = mock_inspector

        from agents.ops_agent import check_celery_health
        result = await check_celery_health()

        assert result["status"] == "ok"
        assert "celery@worker1" in result["workers_up"]
        assert result["workers_down"] == []

    @pytest.mark.asyncio
    @patch("tasks.celery_app.celery_app")
    async def test_no_workers_respond(self, mock_celery):
        mock_inspector = MagicMock()
        mock_inspector.ping.return_value = {}
        mock_inspector.active.return_value = {}
        mock_celery.control.inspect.return_value = mock_inspector

        from agents.ops_agent import check_celery_health
        result = await check_celery_health()

        assert result["status"] == "critical"
        assert result["workers_up"] == []

    @pytest.mark.asyncio
    @patch("tasks.celery_app.celery_app")
    async def test_inspect_exception_returns_critical(self, mock_celery):
        mock_celery.control.inspect.side_effect = Exception("Connection refused")

        from agents.ops_agent import check_celery_health
        result = await check_celery_health()

        assert result["status"] == "critical"
        assert result["workers_up"] == []   # ← change 0 to []
        assert "error" in result


# ---------------------------------------------------------------------------
# ReAct loop — agent.run()
# ---------------------------------------------------------------------------

class TestOpsAgentRun:

    @pytest.mark.asyncio
    @patch("agents.ops_agent.llm_router")
    async def test_scheduled_run_concludes_normally(
        self, mock_router, agent, mock_db
    ):
        """
        Routine scheduled run: LLM calls get_ops_summary once, then concludes.
        """
        summary_result = {
            "bookings": 120, "cancellations": 5,
            "avg_predicted_wait_minutes": 12.3,
            "total_llm_calls": 340, "error_rate_pct": 0.1,
            "voice_calls": 22, "avg_ttfb_seconds": 0.18, "avg_wer": 0.05,
        }

        call_responses = [
            make_llm_response(tool_call_json("get_ops_summary", {"window_hours": 24})),
            make_llm_response(
                "CONCLUDE → System healthy. 120 bookings, avg wait 12.3 min. "
                "WER 5%, TTFB 0.18s — voice pipeline nominal. No action required."
            ),
        ]
        mock_router.call = AsyncMock(side_effect=call_responses)

        with patch("agents.ops_agent._dispatch_tool", new_callable=AsyncMock) as mock_dispatch:
            mock_dispatch.return_value = summary_result
            result = await agent.run("scheduled", {}, mock_db)

        assert "conclusion" in result
        assert result["trigger"] == "scheduled"
        assert len(result["alerts_fired"]) == 0
        assert "healthy" in result["conclusion"].lower() or "nominal" in result["conclusion"].lower()

    @pytest.mark.asyncio
    @patch("agents.ops_agent.llm_router")
    async def test_anomaly_triggers_alert_and_slots(
        self, mock_router, agent, mock_db
    ):
        """
        Surge + anomaly score below threshold → suggest_open_slots + trigger_alert.
        Confirm that both side effects are recorded in the return value.
        """
        tool_sequence = [
            tool_call_json("query_booking_volume", {"window_min": 30}),
            tool_call_json("score_anomaly", {"booking_vector": [3, 4, 3, 18, 22, 31]}),
            tool_call_json("query_prometheus", {"metric": "mediflow_request_duration_seconds", "window_min": 15}),
            tool_call_json("suggest_open_slots", {"date": "2026-05-08", "specialty": "general", "count": 8, "doctor_id": 3}),
            tool_call_json("trigger_alert", {"message": "Surge confirmed. 8 slots opened.", "severity": "warning", "channel": "admin"}),
        ]
        conclude = "CONCLUDE → Booking surge of 6x normal detected. Score -0.74 confirmed. 8 slots opened for Dr. Iqbal. p95 latency 1.2s — system coping."

        responses = [make_llm_response(t) for t in tool_sequence]
        responses.append(make_llm_response(conclude))
        mock_router.call = AsyncMock(side_effect=responses)

        dispatch_returns = [
            [3, 4, 3, 18, 22, 31],       # query_booking_volume
            -0.74,                       # score_anomaly
            [0.8, 0.9, 1.2, 1.1],        # query_prometheus
            {"slots_created": 8, "doctor_notified": True},   # suggest_open_slots
            {"alert_id": 42, "severity": "warning", "created_at": "2026-05-08T10:00:00"},  # trigger_alert
        ]

        with patch("agents.ops_agent._dispatch_tool", new_callable=AsyncMock) as mock_dispatch:
            mock_dispatch.side_effect = dispatch_returns
            result = await agent.run("prometheus_webhook", {"alertname": "HighBookingVolume"}, mock_db)

        assert result["trigger"] == "prometheus_webhook"
        assert len(result["alerts_fired"]) == 1
        assert result["alerts_fired"][0]["alert_id"] == 42
        assert any("suggest_open_slots" in a for a in result["actions_taken"])
        assert "surge" in result["conclusion"]

    @pytest.mark.asyncio
    @patch("agents.ops_agent.llm_router")
    async def test_drift_triggers_retraining(
        self, mock_router, agent, mock_db
    ):
        """
        MLflow drift trigger → agent verifies drift, sample count ok, enqueues retraining.
        """
        tool_sequence = [
            tool_call_json("get_model_drift_score", {"model_name": "wait_time_model"}),
            tool_call_json("trigger_retraining", {"model_name": "wait_time_model", "reason": "KL=0.15 drift confirmed"}),
            tool_call_json("trigger_alert", {"message": "Drift on wait_time_model: KL=0.15. Retraining enqueued.", "severity": "warning", "channel": "admin"}),
        ]
        conclude = "CONCLUDE → wait_time_model drift confirmed (KL=0.15, 312 samples). Retraining task queued."

        responses = [make_llm_response(t) for t in tool_sequence]
        responses.append(make_llm_response(conclude))
        mock_router.call = AsyncMock(side_effect=responses)

        dispatch_returns = [
            {"model_name": "wait_time_model", "kl_divergence": 0.15, "sample_count": 312, "status": "drifted"},
            {"task_id": "abc-123", "model_name": "wait_time_model", "queued_at": "2026-05-08T03:00:00"},
            {"alert_id": 7, "severity": "warning", "created_at": "2026-05-08T03:00:01"},
        ]

        with patch("agents.ops_agent._dispatch_tool", new_callable=AsyncMock) as mock_dispatch:
            mock_dispatch.side_effect = dispatch_returns
            result = await agent.run("mlflow_drift", {"model_name": "wait_time_model", "kl_divergence": 0.15}, mock_db)

        assert any("trigger_retraining" in a for a in result["actions_taken"])
        assert "KL" in result["conclusion"] or "drift" in result["conclusion"].lower()

    @pytest.mark.asyncio
    @patch("agents.ops_agent.llm_router")
    async def test_drift_insufficient_samples_no_retrain(
        self, mock_router, agent, mock_db
    ):
        """
        Drift score > 0.1 BUT sample_count < 200 → info alert, NO retraining.
        This is the guard that prevents premature retraining.
        """
        tool_sequence = [
            tool_call_json("get_model_drift_score", {"model_name": "patient_load_model"}),
            tool_call_json("trigger_alert", {
                "message": "Drift score 0.12 detected but only 47 samples — insufficient for retraining.",
                "severity": "info", "channel": "ops"
            }),
        ]
        conclude = "CONCLUDE → KL=0.12 exceeds threshold but sample_count=47 < 200. Logged as insufficient_data. No retraining triggered."

        responses = [make_llm_response(t) for t in tool_sequence]
        responses.append(make_llm_response(conclude))
        mock_router.call = AsyncMock(side_effect=responses)

        dispatch_returns = [
            {"model_name": "patient_load_model", "kl_divergence": 0.12, "sample_count": 47, "status": "insufficient_data"},
            {"alert_id": 8, "severity": "info", "created_at": "2026-05-08T03:00:00"},
        ]

        with patch("agents.ops_agent._dispatch_tool", new_callable=AsyncMock) as mock_dispatch:
            mock_dispatch.side_effect = dispatch_returns
            result = await agent.run("mlflow_drift", {"model_name": "patient_load_model"}, mock_db)

        # Retraining must NOT have been triggered
        assert not any("trigger_retraining" in a for a in result["actions_taken"])
        assert "insufficient" in result["conclusion"].lower() or "47" in result["conclusion"]

    @pytest.mark.asyncio
    @patch("agents.ops_agent.llm_router")
    async def test_all_providers_exhausted_fires_fallback_alert(
        self, mock_router, agent, mock_db
    ):
        """
        If AllProvidersExhausted is raised, agent should not crash —
        it should fire a fallback warning alert and return gracefully.
        """
        from services.llm_router import AllProvidersExhausted

        mock_router.call = AsyncMock(side_effect=AllProvidersExhausted())

        with patch("agents.ops_agent.trigger_alert", new_callable=AsyncMock) as mock_alert:
            mock_alert.return_value = {"alert_id": 99}
            result = await agent.run("scheduled", {}, mock_db)

        assert result["trigger"] == "scheduled"
        assert "exhausted" in result["conclusion"].lower()
        mock_alert.assert_called_once()
        call_args = mock_alert.call_args
        assert call_args.kwargs["severity"] == "warning"

    @pytest.mark.asyncio
    @patch("agents.ops_agent.llm_router")
    async def test_max_steps_reached_without_conclude(
        self, mock_router, agent, mock_db
    ):
        """
        If LLM never stops calling tools within MAX_STEPS,
        agent should exit cleanly with a fallback conclusion.
        """
        # Always return a tool call — never a CONCLUDE
        eternal_tool = tool_call_json("query_prometheus", {"metric": "x", "window_min": 5})
        mock_router.call = AsyncMock(return_value=make_llm_response(eternal_tool))

        with patch("agents.ops_agent._dispatch_tool", new_callable=AsyncMock) as mock_dispatch:
            mock_dispatch.return_value = [1.0, 2.0]
            result = await agent.run("scheduled", {}, mock_db)

        assert "MAX_STEPS" in result["conclusion"] or result["steps_taken"] == agent.MAX_STEPS

    @pytest.mark.asyncio
    @patch("agents.ops_agent.llm_router")
    async def test_v5_voice_metrics_trigger_alert(
        self, mock_router, agent, mock_db
    ):
        """
        v5: High WER (>0.20) from Deepgram Nova-3 should trigger a warning alert.
        """
        tool_sequence = [
            tool_call_json("get_ops_summary", {"window_hours": 1}),
            tool_call_json("query_prometheus", {"metric": "mediflow_stt_wer", "window_min": 30}),
            tool_call_json("trigger_alert", {
                "message": "STT WER degraded: avg 0.27 over last 30min. Deepgram Nova-3 may be struggling with Urdish input.",
                "severity": "warning", "channel": "ops"
            }),
        ]
        conclude = "CONCLUDE → WER=0.27 exceeds threshold 0.20. Alert fired. No slot changes — this is a voice quality issue, not a capacity issue."

        responses = [make_llm_response(t) for t in tool_sequence]
        responses.append(make_llm_response(conclude))
        mock_router.call = AsyncMock(side_effect=responses)

        summary = {"bookings": 10, "voice_calls": 8, "avg_wer": 0.27, "avg_ttfb_seconds": 0.21}
        dispatch_returns = [
            summary,
            [0.22, 0.25, 0.28, 0.27, 0.29],  # WER values from Prometheus
            {"alert_id": 55, "severity": "warning", "created_at": "2026-05-08T11:00:00"},
        ]

        with patch("agents.ops_agent._dispatch_tool", new_callable=AsyncMock) as mock_dispatch:
            mock_dispatch.side_effect = dispatch_returns
            result = await agent.run("prometheus_webhook", {"alertname": "HighVoiceWER", "value": "0.27"}, mock_db)

        assert len(result["alerts_fired"]) == 1
        assert "WER" in result["conclusion"] or "voice" in result["conclusion"].lower()
        # Crucially — no slots created (voice quality ≠ capacity problem)
        assert not any("suggest_open_slots" in a for a in result["actions_taken"])
        
    @pytest.mark.asyncio
    @patch("agents.ops_agent.llm_router")
    async def test_celery_all_workers_down_fires_critical(
        self, mock_router, agent, mock_db
    ):
        """
        If check_celery_health returns workers_up=0, agent must fire
        a CRITICAL alert immediately without investigating further.
        """
        tool_sequence = [
            tool_call_json("check_celery_health", {}),
            tool_call_json("trigger_alert", {
                "message": "All Celery workers are down. Scheduling, drift detection, retraining, and prediction resolver are offline.",
                "severity": "CRITICAL",
                "channel": "ops",
            }),
        ]
        conclude = "CONCLUDE → All Celery workers unresponsive. Critical alert fired. No background tasks are running."

        responses = [make_llm_response(t) for t in tool_sequence]
        responses.append(make_llm_response(conclude))
        mock_router.call = AsyncMock(side_effect=responses)

        dispatch_returns = [
            {"workers_up": [], "workers_down": ["celery@worker1"], "active_tasks": {}, "status": "critical"},
            {"alert_id": 10, "severity": "CRITICAL", "created_at": "2026-05-08T10:00:00"},
        ]

        with patch("agents.ops_agent._dispatch_tool", new_callable=AsyncMock) as mock_dispatch:
            mock_dispatch.side_effect = dispatch_returns
            result = await agent.run("scheduled", {}, mock_db)

        assert len(result["alerts_fired"]) == 1
        assert result["alerts_fired"][0]["severity"] == "CRITICAL"
        # Must not open slots or trigger retraining — just alert
        assert not any("suggest_open_slots" in a for a in result["actions_taken"])
        assert not any("trigger_retraining" in a for a in result["actions_taken"])


    @pytest.mark.asyncio
    @patch("agents.ops_agent.llm_router")
    async def test_celery_degraded_fires_warning_not_critical(
        self, mock_router, agent, mock_db
    ):
        """
        If some workers are up but one is down, agent fires WARNING not CRITICAL.
        System is degraded but not completely offline.
        """
        tool_sequence = [
            tool_call_json("check_celery_health", {}),
            tool_call_json("trigger_alert", {
                "message": "Celery worker celery@worker2 is unresponsive. worker1 still active.",
                "severity": "WARNING",
                "channel": "ops",
            }),
        ]
        conclude = "CONCLUDE → One Celery worker down (worker2). worker1 still handling tasks. Warning fired."

        responses = [make_llm_response(t) for t in tool_sequence]
        responses.append(make_llm_response(conclude))
        mock_router.call = AsyncMock(side_effect=responses)

        dispatch_returns = [
            {
                "workers_up": ["celery@worker1"],
                "workers_down": ["celery@worker2"],
                "active_tasks": {"celery@worker1": 2},
                "status": "degraded",
            },
            {"alert_id": 11, "severity": "WARNING", "created_at": "2026-05-08T10:05:00"},
        ]

        with patch("agents.ops_agent._dispatch_tool", new_callable=AsyncMock) as mock_dispatch:
            mock_dispatch.side_effect = dispatch_returns
            result = await agent.run("scheduled", {}, mock_db)

        assert len(result["alerts_fired"]) == 1
        assert result["alerts_fired"][0]["severity"] == "WARNING"
        # Not critical — some workers still up
        assert "CRITICAL" not in str(result["alerts_fired"])