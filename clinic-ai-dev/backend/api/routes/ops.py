import time
from typing import List

from fastapi import APIRouter

from schemas import schemas

router = APIRouter()

_now = int(time.time() * 1000)

MOCK_SUGGESTIONS = [
    {"id": "s1", "title": "Open 8 new slots at 15:00", "impact": "−18 min avg wait", "confidence": 0.92},
    {"id": "s2", "title": "Reassign 4 patients from Dr. Khan → Dr. Malik", "impact": "Balance load 91% → 74%", "confidence": 0.86},
    {"id": "s3", "title": "Send proactive SMS to 12 patients", "impact": "Reduce no-shows by 23%", "confidence": 0.78},
]

MOCK_ACTIVITY = [
    {"id": "seed-0", "type": "booking", "text": "New booking — Sara Khan with Dr. Malik", "time": "just now", "at": _now - 0 * 60000},
    {"id": "seed-1", "type": "ai", "text": "AI agent confirmed appointment via WhatsApp", "time": "1m", "at": _now - 1 * 60000},
    {"id": "seed-2", "type": "reassign", "text": "Patient reassigned: Dr. Khan → Dr. Iqbal", "time": "3m", "at": _now - 3 * 60000},
    {"id": "seed-3", "type": "cancel", "text": "Cancellation — Bilal Raza (10:30 slot)", "time": "5m", "at": _now - 5 * 60000},
    {"id": "seed-4", "type": "voice", "text": "Voice booking completed in Urdu — 38s call", "time": "7m", "at": _now - 7 * 60000},
    {"id": "seed-5", "type": "walkin", "text": "Walk-in registered — Hassan Ahmed", "time": "9m", "at": _now - 9 * 60000},
]

MOCK_AGENTS = [
    {"id": "booking", "name": "Booking Agent", "state": "online", "lastAction": "Language detected · ready", "lastSeenAt": _now},
    {"id": "calling", "name": "Calling Agent", "state": "online", "lastAction": "Voice channel idle", "lastSeenAt": _now - 22000},
    {"id": "scheduling", "name": "Scheduling Agent", "state": "online", "lastAction": "Next run in 30m", "lastSeenAt": _now - 120000},
    {"id": "ops_monitor", "name": "Ops Monitor Agent", "state": "online", "lastAction": "Monitoring Prometheus alerts", "lastSeenAt": _now - 15000},
]

MOCK_METRICS = {
    "bookingVolume30m": 42,
    "p95LatencyMs": 1200,
    "apiErrorRatePct": 1.6,
    "anomalyScore": 0.32,
    "waitModelDriftKl": 0.06,
    "keyPoolAvailable": {"gemini": 11, "groq": 18, "together": 7, "openrouter": 4},
}


@router.get("/suggestions", response_model=List[schemas.Suggestion])
def get_suggestions():
    return MOCK_SUGGESTIONS


@router.get("/activity", response_model=List[schemas.ActivityEvent])
def get_activity():
    return MOCK_ACTIVITY


@router.get("/agents", response_model=List[schemas.AgentStatus])
def get_agents():
    return MOCK_AGENTS


@router.get("/metrics", response_model=schemas.ClinicMetrics)
def get_metrics():
    return MOCK_METRICS
