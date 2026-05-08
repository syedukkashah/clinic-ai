import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from agents.orchestrator import orchestrator
from core.config import settings
from db import crud
from db.session import get_db
from schemas import schemas

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Muhammad's existing endpoints (real crud calls)
# ---------------------------------------------------------------------------

@router.get("/suggestions", response_model=List[schemas.Suggestion])
async def get_suggestions(db: AsyncSession = Depends(get_db)):
    # Pull unacknowledged alerts and extract their recommended actions as suggestions
    alerts = await crud.get_ops_alerts(db)

    suggestions = []
    for alert in alerts:
        details = getattr(alert, "details", {}) or {}
        actions = details.get("recommendedActions", [])
        for i, action in enumerate(actions):
            suggestions.append({
                "id": f"alt-{alert.id}-s{i}",
                "title": action,
                "impact": str(details.get("reasoning", ""))[:80],
                "confidence": 0.85 if str(alert.severity).upper() == "CRITICAL" else 0.72,
            })

    # Fallback if no active alerts
    if not suggestions:
        suggestions = [
            {"id": "s1", "title": "Open 8 new slots at 15:00", "impact": "−18 min avg wait", "confidence": 0.92},
            {"id": "s2", "title": "Reassign 4 patients from Dr. Khan → Dr. Malik", "impact": "Balance load 91% → 74%", "confidence": 0.86},
            {"id": "s3", "title": "Send proactive SMS to 12 patients", "impact": "Reduce no-shows by 23%", "confidence": 0.78},
        ]

    return suggestions


@router.get("/activity", response_model=List[schemas.ActivityEvent])
async def get_activity(db: AsyncSession = Depends(get_db)):
    return await crud.get_activity_feed(db)


@router.get("/agents", response_model=List[schemas.AgentStatus])
async def get_agents():
    _now = int(time.time() * 1000)
    return [
        {"id": "booking", "name": "Booking Agent", "state": "online",
         "lastAction": "Listening for requests", "lastSeenAt": _now},
        {"id": "calling", "name": "Calling Agent", "state": "online",
         "lastAction": "Idle", "lastSeenAt": _now - 10000},
        {"id": "scheduling", "name": "Scheduling Agent", "state": "online",
         "lastAction": "Next optimization in 30m", "lastSeenAt": _now - 50000},
        {"id": "ops_monitor", "name": "Ops Monitor Agent", "state": "online",
         "lastAction": "Analyzing drift", "lastSeenAt": _now - 2000},
    ]


@router.get("/metrics", response_model=schemas.ClinicMetrics)
async def get_metrics(db: AsyncSession = Depends(get_db)):
    return await crud.get_dynamic_metrics(db)


# ---------------------------------------------------------------------------
# Pydantic models for webhook
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Ops Monitor Agent endpoints
# ---------------------------------------------------------------------------

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
    alerts = await crud.get_ops_alerts(db, limit=limit, severity=severity)
    return [
        {
            "id": a.id,
            "message": a.message,
            "severity": str(a.severity).lower(),
            "channel": a.channel,
            "agent": a.agent,
            "created_at": a.created_at.isoformat(),
        }
        for a in alerts
    ]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

async def _run_ops_agent_safe(
    trigger: str, context: Dict, db: AsyncSession
) -> None:
    try:
        await orchestrator.run_ops_monitor(trigger=trigger, context=context, db=db)
    except Exception as exc:
        logger.error(
            "OpsAgent background run failed — trigger=%s error=%s",
            trigger, exc, exc_info=True,
        )