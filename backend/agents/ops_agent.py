"""
backend/agents/ops_agent.py

Ops Monitor Agent — AIOps brain for MediFlow.
Triggered by:
  - Celery beat every 10 min (routine check)
  - Prometheus alertmanager webhook (metric thresholds breached)
  - SchedulingAgent on critical overload flag
  - MLflow callback when drift score exceeds 0.1

Architecture:
  - ReAct loop (prompt-based JSON tool calls, same pattern as BookingAgent)
  - MAX_STEPS = 8  (more headroom than BookingAgent — ops traces are longer)
  - task_type = "ops"  → LLM Router routes to ["groq", "gemini"]
  - No Redis memory — ops runs are stateless, each trigger is independent
  - All actions (alerts, slot creation, retraining) are written to PostgreSQL

v5 note: voice_service.py now emits TTFB, WER, and provider-switch metrics.
         This agent queries and reasons about those in addition to the v4 set.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx
import joblib
import numpy as np
from prometheus_client import Counter, Gauge, Histogram
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from db import crud
from db.models import (
    AppointmentStatus,
    BookingChannel,
    OpsAlert,
    OpsAlertSeverity,
)
from services.agent_run_logger import providers_from_steps
from services.llm_router import AllProvidersExhausted, llm_router

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prometheus metrics emitted BY this agent
# (metric names must match exactly what Grafana Dashboard 2 & 3 expect)
# ---------------------------------------------------------------------------
PROM_OPS_RUNS = Counter(
    "mediflow_ops_agent_runs_total",
    "Ops Monitor Agent invocations",
    ["trigger"],
)
PROM_OPS_STEPS = Counter(
    "mediflow_ops_agent_steps_total",
    "Tool calls made by Ops Monitor Agent",
    ["tool"],
)
PROM_OPS_ALERTS = Counter(
    "mediflow_ops_alerts_total",
    "Alerts triggered by Ops Monitor Agent",
    ["severity"],
)
PROM_OPS_RETRAINS = Counter(
    "mediflow_retraining_triggers_total",
    "Retraining tasks enqueued",
    ["model_name", "reason_type"],
)
PROM_ANOMALY_SCORE = Gauge(
    "mediflow_anomaly_score",
    "Isolation Forest anomaly score (lower = more anomalous)",
)
PROM_REASSIGN = Counter(
    "mediflow_reassignments_total",
    "Appointment slot reassignments triggered by agents",
)

PROM_CELERY_WORKERS = Gauge(
    "mediflow_celery_workers_up",
    "Number of responsive Celery workers",
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_STEPS = 8
ANOMALY_MODEL_PATH = "/models/anomaly_detector.pkl"
PROMETHEUS_BASE = settings.PROMETHEUS_URL  # e.g. "http://prometheus:9090"
DRIFT_THRESHOLD = 0.1
ANOMALY_THRESHOLD = -0.3
WAIT_WARN_THRESHOLD = 35       # minutes — flag overloaded doctor
WAIT_CRITICAL_THRESHOLD = 45   # minutes — trigger reassignment
P95_THRESHOLD_SECONDS = 2.0    # API latency SLO

# v5 voice thresholds (from voice_service.py metrics)
TTFB_WARN_SECONDS = 1.5        # Deepgram Aura should be <200ms; raise at 1.5s
WER_WARN_THRESHOLD = 0.20      # 20% word-error rate is degraded STT quality

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """
You are the MediFlow Ops Monitor Agent — the AIOps brain of a bilingual AI clinic
operations system. You reason about operational data and take targeted actions.

You are NOT a passive monitoring dashboard. You actively investigate, confirm,
and respond to anomalies using the tools available to you.

=== REASONING STYLE ===
Follow a strict Think → Act → Observe loop:
  THINK: What does the trigger tell me? What do I need to verify first?
  ACT: Call exactly one tool.
  OBSERVE: What did the result tell me? Does it confirm or contradict my hypothesis?
Repeat until you have enough evidence to either dismiss the alert or act on it.
Always confirm an anomaly with at least TWO independent signals before escalating
to severity="critical". One signal → "warning".

=== TOOLS ===
You have 9 tools. Call them as JSON:
{"tool": "<name>", "args": {<key>: <value>}}

1. query_prometheus(metric: str, window_min: int) -> list[float]
   Query a Prometheus metric over the last N minutes. Returns time-series values.
   Metric names available:
     mediflow_requests_total, mediflow_request_duration_seconds (p50/p95/p99),
     mediflow_llm_calls_total, mediflow_llm_latency_seconds,
     mediflow_appointments_booked_total, mediflow_anomaly_score,
     mediflow_key_pool_available, mediflow_model_drift_score,
     mediflow_stt_calls_total, mediflow_stt_latency_seconds,
     mediflow_voice_ttfb_seconds [v5], mediflow_stt_wer [v5],
     mediflow_voice_provider_switches_total [v5]

2. query_booking_volume(window_min: int) -> list[int]
   Returns bookings per 5-minute bucket over the last N minutes.
   Use this as input to score_anomaly.

3. score_anomaly(booking_vector: list[int]) -> float
   Runs Isolation Forest on the booking volume vector.
   Returns score in [-1.0, 1.0]. Below -0.3 = anomaly confirmed.

4. trigger_alert(message: str, severity: str, channel: str) -> dict
   severity: "INFO" | "WARNING" | "CRITICAL"
   channel: "admin" | "ops" | "all"
   Write full reasoning context into message — this is what the admin reads.
   Returns {"alert_id": int, "created_at": str}

5. suggest_open_slots(date: str, specialty: str, count: int, doctor_id: int) -> dict
   Creates N new appointment slots for the given doctor and notifies them.
   date: "YYYY-MM-DD". doctor_id is REQUIRED — never omit it.
   Returns {"slots_created": int, "doctor_notified": bool}

6. trigger_retraining(model_name: str, reason: str) -> dict
   Enqueues a Celery retraining task for "wait_time_model" or "patient_load_model".
   Only call this when drift is confirmed (score > 0.1) AND samples >= 200.
   Returns {"task_id": str, "queued_at": str}

7. get_model_drift_score(model_name: str) -> dict
   Returns {"model_name": str, "kl_divergence": float, "sample_count": int,
            "status": "ok"|"drifted"|"insufficient_data"}
   If sample_count < 200, status will be "insufficient_data" — do NOT retrain.

8. get_ops_summary(window_hours: int = 24) -> dict
   Returns aggregate stats: bookings, cancellations, avg_wait, llm_calls,
   error_rate, voice_calls, avg_ttfb_seconds [v5], avg_wer [v5].
   Use as first step in scheduled/routine triggers for orientation.
   
9. check_celery_health() -> dict
   Pings all Celery workers. Returns workers_up (list), workers_down (list),
   active_tasks (dict), status ("ok"|"degraded"|"critical").
   Call on every scheduled check and whenever background features seem silent.

=== DECISION RULES ===
- Booking surge + anomaly score < -0.3 → suggest_open_slots + trigger_alert("WARNING")
- Booking surge + score < -0.5 + p95 > 2s → trigger_alert("CRITICAL") + suggest_open_slots
- Drift score > 0.1 AND samples >= 200 → trigger_retraining + trigger_alert("WARNING")
- Drift score > 0.1 AND samples < 200 → trigger_alert("INFO", note insufficient data)
- p95 latency > 2.0s alone → trigger_alert("WARNING"), do NOT open slots
- Key pool for any provider drops to 0 → trigger_alert("WARNING")
- STT WER > 0.20 [v5] → trigger_alert("WARNING") mentioning voice degradation
- Voice TTFB > 1.5s [v5] → trigger_alert("WARNING") mentioning TTS latency
- All metrics normal → return summary without triggering any alert
- Celery workers_up == 0 → trigger_alert("CRITICAL") immediately — do not investigate further
- Celery workers_down is non-empty but workers_up > 0 → trigger_alert("WARNING")
- On scheduled checks, call check_celery_health as part of routine orientation

=== RESPONSE FORMAT ===
After your reasoning loop, end with a plain-language CONCLUDE block:
CONCLUDE → <one paragraph summary of what you found, what you did, and why>
Do NOT use bullet points in CONCLUDE. Write it as a log entry for the admin dashboard.
"""

# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

async def query_prometheus(metric: str, window_min: int) -> List[float]:
    """
    Query Prometheus instant values over a range window.
    Returns list of float values (one per scrape interval).
    """
    end = datetime.utcnow()
    start = end - timedelta(minutes=window_min)
    step = max(15, window_min * 6)  # ~10 data points minimum

    params = {
        "query": metric,
        "start": start.isoformat() + "Z",
        "end": end.isoformat() + "Z",
        "step": f"{step}s",
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{PROMETHEUS_BASE}/api/v1/query_range", params=params
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("data", {}).get("result", [])
            if not results:
                return []
            # Flatten all series values into a single list of floats
            values = []
            for series in results:
                for _, val in series.get("values", []):
                    try:
                        values.append(float(val))
                    except (ValueError, TypeError):
                        pass
            return values
    except Exception as exc:
        logger.warning("Prometheus query failed for %s: %s", metric, exc)
        return []


async def query_booking_volume(db: AsyncSession, window_min: int) -> List[int]:
    """
    Returns bookings-per-5-minute bucket for the last N minutes.
    Queries PostgreSQL directly (faster than Prometheus for exact counts).
    """
    cutoff = datetime.utcnow() - timedelta(minutes=window_min)
    rows = await crud.get_booking_counts_bucketed(db, since=cutoff, bucket_minutes=5)
    # rows: list of (bucket_start, count) ordered ascending
    return [int(r.count) for r in rows]


def score_anomaly(booking_vector: List[int]) -> float:
    """
    Runs Isolation Forest on booking volume vector.
    Returns score in [-1.0, 1.0]. Below ANOMALY_THRESHOLD (-0.3) = anomaly.
    Loads model from disk (joblib). Model trained in Week 5 by M6.
    """
    if not booking_vector or len(booking_vector) < 2:
        return 0.0  # insufficient data — don't even load model

    try:
        model = joblib.load(ANOMALY_MODEL_PATH)
    except FileNotFoundError:
        logger.warning(
            "Anomaly model not found at %s — returning neutral score 0.0",
            ANOMALY_MODEL_PATH,
        )
        return 0.0

    X = np.array(booking_vector).reshape(1, -1)

    try:
        score = float(model.decision_function(X)[0])
    except ValueError:
        n_features = model.n_features_in_
        if len(booking_vector) < n_features:
            X = np.pad(X, ((0, 0), (0, n_features - X.shape[1])), constant_values=0)
        else:
            X = X[:, :n_features]
        score = float(model.decision_function(X)[0])

    PROM_ANOMALY_SCORE.set(score)
    return score


async def trigger_alert(
    db: AsyncSession,
    message: str,
    severity: str,
    channel: str,
) -> Dict[str, Any]:
    """
    Writes alert to ops_alerts table and emits Prometheus counter.
    severity: "INFO" | "WARNING" | "CRITICAL"
    channel:  "admin" | "ops" | "all"
    """
    valid_severities = {"INFO", "WARNING", "CRITICAL"}
    if severity not in valid_severities:
        severity = "WARNING"

    alert = await crud.create_ops_alert(db, {
        "title": message,
        "severity": severity,
        "type": "ops_monitor",
        "reasoning": message,
        "trace": [],
        "recommendedActions": [],
    })
    PROM_OPS_ALERTS.labels(severity=severity).inc()

    return {
        "alert_id": alert["id"],
        "severity": severity,
        "created_at": alert["timestamp"],
    }


async def suggest_open_slots(
    db: AsyncSession,
    date: str,
    specialty: str,
    count: int,
    doctor_id: int,
) -> Dict[str, Any]:
    """
    Creates N new appointment slots for the given doctor and notifies them.
    doctor_id is REQUIRED (validated by LLM via system prompt rule).
    """
    try:
        date_obj = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        return {"slots_created": 0, "doctor_notified": False, "error": "Invalid date format"}

    slots = await crud.create_slots_for_doctor(
        db,
        doctor_id=doctor_id,
        date=date_obj,
        specialty=specialty,
        count=count,
    )

    notified = False
    if slots:
        await crud.create_notification(
            db,
            recipient_id=doctor_id,
            recipient_type="doctor",
            message=f"[Ops Agent] {count} new slots opened for you on {date} due to predicted high patient load.",
            lang="en",
        )
        notified = True
        PROM_REASSIGN.inc(count)

    logger.info(
        "OpsAgent: created %d slots for doctor_id=%d on %s", len(slots), doctor_id, date
    )
    return {"slots_created": len(slots), "doctor_notified": notified}


async def trigger_retraining(model_name: str, reason: str) -> Dict[str, Any]:
    """
    Enqueues a Celery retraining task.
    Only call when drift confirmed AND sample_count >= 200.
    """
    valid_models = {"wait_time_model", "patient_load_model"}
    if model_name not in valid_models:
        return {"error": f"Unknown model: {model_name}"}

    # Import here to avoid circular imports at module load time
    from tasks.celery_app import celery_app

    task = celery_app.send_task(
        "training.retrain_model",
        kwargs={"model_name": model_name, "reason": reason},
    )
    reason_type = "drift" if "drift" in reason.lower() else "scheduled"
    PROM_OPS_RETRAINS.labels(model_name=model_name, reason_type=reason_type).inc()
    logger.info("OpsAgent: retraining enqueued for %s — %s", model_name, reason)

    return {
        "task_id": task.id,
        "model_name": model_name,
        "reason": reason,
        "queued_at": datetime.utcnow().isoformat(),
    }


async def get_model_drift_score(model_name: str, db: AsyncSession) -> Dict[str, Any]:
    """
    Computes KL divergence between recent predictions and baseline distribution.
    Reads from ml_predictions table (resolved rows only).
    Returns status: "ok" | "drifted" | "insufficient_data"
    """
    from scipy.stats import entropy

    MIN_SAMPLES = 200
    cutoff = datetime.utcnow() - timedelta(hours=24)

    recent_preds = await crud.get_recent_predictions(
        db, model_name=model_name, since=cutoff, resolved_only=True
    )
    sample_count = len(recent_preds)

    if sample_count < MIN_SAMPLES:
        logger.info(
            "Drift check for %s: only %d samples (need %d) — skipping",
            model_name, sample_count, MIN_SAMPLES,
        )
        return {
            "model_name": model_name,
            "kl_divergence": None,
            "sample_count": sample_count,
            "status": "insufficient_data",
        }

    baseline = await crud.get_baseline_distribution(db, model_name=model_name)
    if not baseline:
        return {
            "model_name": model_name,
            "kl_divergence": None,
            "sample_count": sample_count,
            "status": "insufficient_data",
        }

    bins = 20
    p_vals = np.array([r.predicted_value for r in recent_preds])
    q_vals = np.array(baseline)

    p_hist, _ = np.histogram(p_vals, bins=bins, density=True)
    q_hist, _ = np.histogram(q_vals, bins=bins, density=True)
    p_hist += 1e-10
    q_hist += 1e-10

    kl = float(entropy(p_hist, q_hist))
    status = "drifted" if kl > DRIFT_THRESHOLD else "ok"

    from services.monitoring_service import PROM_DRIFT_SCORE
    PROM_DRIFT_SCORE.labels(model=model_name).set(kl)

    logger.info("Drift score for %s: KL=%.4f status=%s", model_name, kl, status)
    return {
        "model_name": model_name,
        "kl_divergence": round(kl, 4),
        "sample_count": sample_count,
        "status": status,
    }


async def get_ops_summary(db: AsyncSession, window_hours: int = 24) -> Dict[str, Any]:
    """
    Aggregate operational stats for the last N hours.
    Includes v5 voice metrics (avg_ttfb, avg_wer) from Prometheus.
    """
    since = datetime.utcnow() - timedelta(hours=window_hours)

    bookings = await crud.count_appointments_since(db, since=since)
    cancellations = await crud.count_cancellations_since(db, since=since)
    avg_wait = await crud.get_avg_predicted_wait(db, since=since)

    llm_calls = await query_prometheus(
        "mediflow_llm_calls_total", window_min=window_hours * 60
    )
    error_rates = await query_prometheus(
        'mediflow_requests_total{status_code=~"5.."}', window_min=window_hours * 60
    )
    voice_calls = await query_prometheus(
        "mediflow_stt_calls_total", window_min=window_hours * 60
    )
    # v5 voice metrics
    ttfb_vals = await query_prometheus(
        "mediflow_voice_ttfb_seconds", window_min=window_hours * 60
    )
    wer_vals = await query_prometheus(
        "mediflow_stt_wer", window_min=window_hours * 60
    )

    return {
        "window_hours": window_hours,
        "bookings": bookings,
        "cancellations": cancellations,
        "avg_predicted_wait_minutes": round(avg_wait or 0, 1),
        "total_llm_calls": int(sum(llm_calls)) if llm_calls else 0,
        "error_rate_pct": round(
            (sum(error_rates) / max(sum(llm_calls), 1)) * 100, 2
        ) if error_rates else 0.0,
        "voice_calls": int(sum(voice_calls)) if voice_calls else 0,
        # v5 additions
        "avg_ttfb_seconds": round(float(np.mean(ttfb_vals)), 3) if ttfb_vals else None,
        "avg_wer": round(float(np.mean(wer_vals)), 3) if wer_vals else None,
    }

async def check_celery_health() -> Dict[str, Any]:
    """
    Pings all Celery workers via the inspect API.
    Returns which workers are up, which are down, and what tasks are active.
    Timeout of 3s — if a worker doesn't respond in time, it's considered dead.
    """
    from tasks.celery_app import celery_app
    import asyncio

    def _inspect():
        inspector = celery_app.control.inspect(timeout=3.0)
        ping = inspector.ping() or {}
        active = inspector.active() or {}
        return ping, active

    try:
        ping, active = await asyncio.to_thread(_inspect)
    except Exception as exc:
        logger.error("Celery inspect failed: %s", exc)
        PROM_CELERY_WORKERS.set(0)
        return {
            "workers_up": [],        # ← was 0, change to []
            "workers_down": ["inspect_failed"],
            "active_tasks": {},
            "status": "critical",
            "error": str(exc),
        }

    workers_up = list(ping.keys())
    workers_down = []

    # Expected workers defined in docker-compose — flag any that don't respond
    expected = getattr(settings, "EXPECTED_CELERY_WORKERS", [])
    if expected:
        workers_down = [w for w in expected if w not in workers_up]

    PROM_CELERY_WORKERS.set(len(workers_up))

    status = "critical" if len(workers_up) == 0 else (
        "degraded" if workers_down else "ok"
    )

    logger.info(
        "Celery health: %d workers up, %d down, status=%s",
        len(workers_up), len(workers_down), status
    )

    return {
        "workers_up": workers_up,
        "workers_down": workers_down,
        "active_tasks": {w: len(t) for w, t in active.items()},
        "status": status,
    }


# ---------------------------------------------------------------------------
# Tool registry — maps name → callable for dispatch
# ---------------------------------------------------------------------------
TOOL_SCHEMAS = [
    {
        "name": "query_prometheus",
        "description": "Query a Prometheus metric time-series over a window.",
        "parameters": {
            "metric": "string — exact Prometheus metric name",
            "window_min": "int — lookback window in minutes",
        },
    },
    {
        "name": "query_booking_volume",
        "description": "Return bookings-per-5-minute bucket list for anomaly scoring.",
        "parameters": {"window_min": "int"},
    },
    {
        "name": "score_anomaly",
        "description": "Run Isolation Forest on booking vector. Returns float score.",
        "parameters": {"booking_vector": "list[int]"},
    },
    {
        "name": "trigger_alert",
        "description": "Write alert to DB and admin dashboard.",
        "parameters": {
            "message": "string — full context for admin",
            "severity": "INFO | WARNING | CRITICAL",
            "channel": "admin | ops | all",
        },
    },
    {
        "name": "suggest_open_slots",
        "description": "Create N slots for a doctor and notify them. doctor_id required.",
        "parameters": {
            "date": "YYYY-MM-DD",
            "specialty": "string",
            "count": "int",
            "doctor_id": "int — REQUIRED",
        },
    },
    {
        "name": "trigger_retraining",
        "description": "Enqueue Celery retraining for a model. Only after drift confirmed.",
        "parameters": {
            "model_name": "wait_time_model | patient_load_model",
            "reason": "string",
        },
    },
    {
        "name": "get_model_drift_score",
        "description": "Compute KL divergence for a model vs baseline.",
        "parameters": {"model_name": "wait_time_model | patient_load_model"},
    },
    {
        "name": "get_ops_summary",
        "description": "Aggregate stats for last N hours. Use as first step on routine triggers.",
        "parameters": {"window_hours": "int (default 24)"},
    },
    {
        "name": "check_celery_health",
        "description": (
            "Ping all Celery workers. Returns which are up/down and active task counts. "
            "Call this when: scheduled check, any background feature seems silent, "
            "or drift/retraining/scheduling appears to have stopped working."
        ),
        "parameters": {},
    }
]


async def _dispatch_tool(
    tool_call: Dict[str, Any],
    db: AsyncSession,
) -> Any:
    """
    Dispatch a tool call from the LLM to the correct function.
    All tools that touch DB receive the session as an injected arg.
    """
    name = tool_call.get("tool", "")
    args = tool_call.get("args", {})

    PROM_OPS_STEPS.labels(tool=name).inc()

    if name == "query_prometheus":
        return await query_prometheus(**args)

    elif name == "query_booking_volume":
        return await query_booking_volume(db, **args)

    elif name == "score_anomaly":
        return score_anomaly(**args)

    elif name == "trigger_alert":
        return await trigger_alert(db, **args)

    elif name == "suggest_open_slots":
        return await suggest_open_slots(db, **args)

    elif name == "trigger_retraining":
        return await trigger_retraining(**args)

    elif name == "get_model_drift_score":
        return await get_model_drift_score(**args, db=db)

    elif name == "get_ops_summary":
        return await get_ops_summary(db, **args)
    
    elif name == "check_celery_health":
        return await check_celery_health()
    
    else:
        logger.warning("OpsAgent: unknown tool requested: %s", name)
        return {"error": f"Unknown tool: {name}"}


# ---------------------------------------------------------------------------
# Main Agent class
# ---------------------------------------------------------------------------
class OpsMonitorAgent:
    """
    AIOps Ops Monitor Agent.

    Entry point: run(trigger, context, db)
    trigger: "scheduled" | "prometheus_webhook" | "scheduling_overload" | "mlflow_drift"
    context: dict with trigger-specific metadata (e.g. metric name, alert labels)
    db: AsyncSession injected by caller (FastAPI lifespan or Celery task)
    """

    MAX_STEPS = 8

    async def run(
        self,
        trigger: str,
        context: Optional[Dict[str, Any]],
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Execute the ReAct reasoning loop for this ops event.

        Returns:
          {
            "trigger": str,
            "steps_taken": int,
            "conclusion": str,
            "alerts_fired": list[dict],
            "actions_taken": list[str],
          }
        """
        PROM_OPS_RUNS.labels(trigger=trigger).inc()
        context = context or {}
        started_at = datetime.now(timezone.utc)
        run_started = time.perf_counter()

        logger.info("OpsAgent starting — trigger=%s context=%s", trigger, context)

        # Build the initial user message that seeds the reasoning loop
        user_message = self._build_trigger_message(trigger, context)

        messages: List[Dict[str, Any]] = [{"role": "user", "content": user_message}]

        alerts_fired: List[Dict] = []
        actions_taken: List[str] = []
        trace: List[Dict[str, Any]] = []
        conclusion = ""

        try:
            for step in range(self.MAX_STEPS):
                # Pick task type: use "ops" routing (groq → gemini)
                llm_started = time.perf_counter()
                llm_resp = await llm_router.call(
                    messages=messages,
                    system=SYSTEM_PROMPT,
                    task_type="ops",
                    tools=[{"name": t["name"], "description": t["description"],
                            "parameters": t["parameters"]} for t in TOOL_SCHEMAS],
                )
                llm_latency_ms = int((time.perf_counter() - llm_started) * 1000)

                content = llm_resp.text if hasattr(llm_resp, "text") else str(llm_resp)
                provider = getattr(llm_resp, "provider", "unknown")

                # Check if LLM returned a tool call (JSON) or a final conclusion
                tool_call = self._parse_tool_call(content)

                if tool_call is None:
                    # No tool call — this is the final CONCLUDE response
                    conclusion = content
                    trace.append({
                        "type": "CONCLUDE",
                        "tool": "ops_monitor",
                        "provider": provider,
                        "args": {"trigger": trigger},
                        "result": content[:500],
                        "latencyMs": llm_latency_ms,
                    })
                    logger.info("OpsAgent concluded after %d steps", step + 1)
                    break

                # Execute the tool
                logger.info(
                    "OpsAgent step %d — tool: %s args: %s",
                    step + 1, tool_call.get("tool"), tool_call.get("args", {}),
                )

                trace.append({
                    "type": "ACT",
                    "tool": tool_call.get("tool"),
                    "provider": provider,
                    "args": tool_call.get("args", {}),
                    "result": "Tool call selected by LLM",
                    "latencyMs": llm_latency_ms,
                })
                tool_started = time.perf_counter()
                try:
                    result = await _dispatch_tool(tool_call, db)
                except Exception as exc:
                    result = {"error": str(exc)}
                    logger.error(
                        "OpsAgent tool error [%s]: %s", tool_call.get("tool"), exc
                    )
                tool_latency_ms = int((time.perf_counter() - tool_started) * 1000)
                trace.append({
                    "type": "OBSERVE",
                    "tool": tool_call.get("tool"),
                    "provider": provider,
                    "args": tool_call.get("args", {}),
                    "result": json.dumps(result, default=str)[:500],
                    "latencyMs": tool_latency_ms,
                })

                # Track side effects for return value
                if tool_call.get("tool") == "trigger_alert" and isinstance(result, dict):
                    alerts_fired.append(result)
                elif tool_call.get("tool") in (
                    "suggest_open_slots", "trigger_retraining"
                ):
                    actions_taken.append(
                        f"{tool_call['tool']}({tool_call.get('args', {})})"
                    )

                # Feed result back into conversation as tool-result message
                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "user",
                    "content": f"[Tool result for {tool_call.get('tool')}]: "
                               f"{json.dumps(result, default=str)}",
                })

            else:
                # Exhausted MAX_STEPS without a CONCLUDE — force a summary
                conclusion = (
                    f"Ops Agent exhausted {self.MAX_STEPS} steps on trigger '{trigger}'. "
                    "Check logs for full reasoning trace."
                )
                logger.warning("OpsAgent: MAX_STEPS reached without CONCLUDE")

        except AllProvidersExhausted:
            conclusion = (
                f"All LLM providers exhausted during ops check (trigger={trigger}). "
                "Manual review required."
            )
            logger.error("OpsAgent: AllProvidersExhausted — ops run aborted")
            # Still fire a fallback alert so the admin knows
            await trigger_alert(
                db,
                message=conclusion,
                severity="warning",
                channel="ops",
            )
            trace.append({
                "type": "CONCLUDE",
                "tool": "ops_monitor",
                "provider": "none",
                "args": {"trigger": trigger},
                "result": conclusion,
                "latencyMs": int((time.perf_counter() - run_started) * 1000),
            })

        steps_taken = (len(messages) - 1) // 2  # each step = assistant + tool-result pair
        clean_conclusion = conclusion.replace("CONCLUDE â†’", "").strip()
        clean_conclusion = clean_conclusion.replace("CONCLUDE", "").replace("->", "").strip(" -:")
        outcome = "alerted" if alerts_fired else "acted" if actions_taken else "normal"
        await crud.create_agent_run(
            db,
            {
                "agent": "ops_monitor",
                "trigger": trigger,
                "outcome": outcome,
                "steps_count": len(trace),
                "duration_ms": int((time.perf_counter() - run_started) * 1000),
                "providers_used": providers_from_steps(trace),
                "tool_calls": trace,
                "summary": clean_conclusion[:500],
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc),
            },
        )

        return {
            "trigger": trigger,
            "steps_taken": steps_taken,
            "conclusion": conclusion.replace("CONCLUDE →", "").strip(),
            "conclusion": clean_conclusion,
            "alerts_fired": alerts_fired,
            "actions_taken": actions_taken,
            "tool_calls": trace,
        }

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _build_trigger_message(
        self, trigger: str, context: Dict[str, Any]
    ) -> str:
        """
        Convert trigger + context into a natural-language seed message
        that gives the LLM enough orientation to start reasoning.
        """
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        if trigger == "scheduled":
            return (
                f"[{ts}] Routine scheduled check. "
                "Start with get_ops_summary to get a 24h overview, then decide "
                "whether any metric warrants deeper investigation."
            )

        elif trigger == "prometheus_webhook":
            alert_name = context.get("alertname", "unknown")
            labels = context.get("labels", {})
            value = context.get("value", "unknown")
            return (
                f"[{ts}] Prometheus alert fired: {alert_name}. "
                f"Labels: {labels}. Reported value: {value}. "
                "Investigate and determine whether this is a confirmed anomaly "
                "or a transient spike. Use at least two tools before concluding."
            )

        elif trigger == "scheduling_overload":
            doctor_id = context.get("doctor_id", "unknown")
            severity = context.get("severity", "warning")
            msg = context.get("message", "")
            return (
                f"[{ts}] SchedulingAgent flagged overload. "
                f"doctor_id={doctor_id}, severity={severity}, message='{msg}'. "
                "Check booking volume and anomaly score to determine if this is "
                "a clinic-wide surge. Open slots only if confirmed."
            )

        elif trigger == "mlflow_drift":
            model_name = context.get("model_name", "unknown")
            kl = context.get("kl_divergence", "unknown")
            return (
                f"[{ts}] MLflow drift callback for model '{model_name}'. "
                f"Reported KL divergence: {kl}. "
                "Verify drift score independently with get_model_drift_score. "
                "Only trigger retraining if sample_count >= 200."
            )

        else:
            return (
                f"[{ts}] Unknown trigger type: '{trigger}'. Context: {context}. "
                "Start with get_ops_summary to orient yourself."
            )

    @staticmethod
    def _parse_tool_call(content: str) -> Optional[Dict[str, Any]]:
        """
        Extract a JSON tool call from LLM output.
        Returns None if content is a plain-text CONCLUDE response.
        """
        content = content.strip()

        # Try direct JSON parse
        if content.startswith("{"):
            try:
                parsed = json.loads(content)
                if "tool" in parsed:
                    return parsed
            except json.JSONDecodeError:
                pass

        # Try extracting JSON from a code block
        if "```" in content:
            try:
                start = content.index("```") + 3
                # skip optional language tag (e.g. ```json)
                if content[start:start+4].lower() == "json":
                    start += 4
                end = content.rindex("```")
                block = content[start:end].strip()
                parsed = json.loads(block)
                if "tool" in parsed:
                    return parsed
            except (ValueError, json.JSONDecodeError):
                pass

        # Try finding embedded JSON object
        try:
            brace_start = content.index("{")
            brace_end = content.rindex("}") + 1
            snippet = content[brace_start:brace_end]
            parsed = json.loads(snippet)
            if "tool" in parsed:
                return parsed
        except (ValueError, json.JSONDecodeError):
            pass

        return None  # It's a CONCLUDE response


# ---------------------------------------------------------------------------
# Module-level singleton (mirrors booking_agent pattern)
# ---------------------------------------------------------------------------
ops_monitor_agent = OpsMonitorAgent()
