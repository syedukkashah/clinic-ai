# ── ADD THESE IMPORTS at the top of ops.py ──────────────────────────────────
import logging
from typing import Any, Dict, Optional
from fastapi import BackgroundTasks, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from agents.orchestrator import orchestrator
from core.config import settings
from db.session import get_db

logger = logging.getLogger(__name__)

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

class AlertmanagerLabel(BaseModel):
    alertname: str
    severity: Optional[str] = None
    class Config:
        extra = "allow"

class AlertmanagerAnnotation(BaseModel):
    summary: Optional[str] = None
    description: Optional[str] = None
    class Config:
        extra = "allow"

class AlertmanagerAlert(BaseModel):
    status: str
    labels: AlertmanagerLabel
    annotations: Optional[AlertmanagerAnnotation] = None
    startsAt: Optional[str] = None
    endsAt: Optional[str] = None
    fingerprint: Optional[str] = None

class AlertmanagerPayload(BaseModel):
    version: str = "4"
    status: str
    alerts: List[AlertmanagerAlert] = []
    groupLabels: Optional[Dict[str, str]] = {}
    commonLabels: Optional[Dict[str, str]] = {}
    commonAnnotations: Optional[Dict[str, str]] = {}

class ManualTriggerRequest(BaseModel):
    trigger: str = "scheduled"
    context: Optional[Dict[str, Any]] = {}


# --- Real endpoints ---

@router.post("/webhook/prometheus", status_code=202)
async def prometheus_webhook(
    payload: AlertmanagerPayload,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    x_alertmanager_token: Optional[str] = Header(None, alias="X-Alertmanager-Token"),
):
    if settings.ALERTMANAGER_WEBHOOK_TOKEN:
        if x_alertmanager_token != settings.ALERTMANAGER_WEBHOOK_TOKEN:
            raise HTTPException(status_code=403, detail="Invalid webhook token")

    firing_alerts = [a for a in payload.alerts if a.status == "firing"]
    if not firing_alerts:
        return {"accepted": True, "firing_count": 0}

    for alert in firing_alerts:
        context = {
            "alertname": alert.labels.alertname,
            "severity": alert.labels.severity or "unknown",
            "labels": alert.labels.model_dump(exclude_none=True),
            "summary": (alert.annotations.summary if alert.annotations else ""),
            "description": (alert.annotations.description if alert.annotations else ""),
        }
        background_tasks.add_task(
            _run_ops_agent_safe, trigger="prometheus_webhook", context=context, db=db
        )

    return {"accepted": True, "firing_count": len(firing_alerts)}


@router.post("/run")
async def manual_run(
    body: ManualTriggerRequest,
    db: AsyncSession = Depends(get_db),
):
    return await orchestrator.run_ops_monitor(
        trigger=body.trigger, context=body.context, db=db
    )


@router.get("/alerts")
async def list_alerts(
    limit: int = Query(default=50, le=200),
    severity: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    from db import crud
    alerts = await crud.get_ops_alerts(db, limit=limit, severity=severity)
    return [
        {"id": a.id, "message": a.message, "severity": a.severity.value.lower(),
         "channel": a.channel, "agent": a.agent, "created_at": a.created_at.isoformat()}
        for a in alerts
    ]


# --- Helper ---

async def _run_ops_agent_safe(trigger: str, context: Dict, db: AsyncSession):
    try:
        await orchestrator.run_ops_monitor(trigger=trigger, context=context, db=db)
    except Exception as exc:
        logger.error("OpsAgent background run failed — trigger=%s error=%s", trigger, exc, exc_info=True)
