from __future__ import annotations

import math
import os
import re
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import (
    AnomalyPrediction,
    AgentRun,
    Appointment,
    AppointmentStatus,
    BookingChannel,
    DailyLoad,
    Doctor,
    MLPrediction,
    Notification,
    OpsAlert,
    Patient,
)
from db.session import get_db
from services.llm_router import llm_router

router = APIRouter()
MLFLOW_BASE_URL = os.getenv("MLFLOW_URL") or os.getenv("MLFLOW_TRACKING_URI") or "http://mlflow:5000"


@router.get("/stats/summary")
async def get_stats_summary(db: AsyncSession = Depends(get_db)):
    today = date.today()
    hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)

    total_today = await _scalar(
        db, select(func.count(Appointment.id)).where(Appointment.date == today)
    )
    booked_last_hour = await _scalar(
        db, select(func.count(Appointment.id)).where(Appointment.created_at >= hour_ago)
    )
    avg_wait = await _scalar(
        db,
        select(func.coalesce(func.avg(Appointment.predicted_wait_min), 0)).where(
            Appointment.date == today
        ),
    )
    reassignments_today = await _scalar(
        db,
        select(func.count(Notification.id)).where(
            Notification.message.ilike("%moved%"),
            func.date(Notification.created_at) == today,
        ),
    )
    notifications_today = await _scalar(
        db, select(func.count(Notification.id)).where(func.date(Notification.created_at) == today)
    )

    return {
        "total_bookings_today": int(total_today or 0),
        "booked_last_hour": int(booked_last_hour or 0),
        "active_sessions": 0,
        "avg_predicted_wait": round(float(avg_wait or 0), 2),
        "llm_calls_last_hour": 0,
        "anomaly_score": await _latest_anomaly_score(db),
        "slot_reassignments_today": int(reassignments_today or 0),
        "notifications_today": int(notifications_today or 0),
    }


@router.get("/appointments")
async def get_admin_appointments(
    db: AsyncSession = Depends(get_db),
    target_date: Optional[date] = Query(None, alias="date"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    doctor_id: Optional[int] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
):
    stmt = (
        select(Appointment)
        .options(selectinload(Appointment.patient), selectinload(Appointment.doctor))
        .order_by(Appointment.scheduled_at.desc())
    )
    count_stmt = select(func.count(Appointment.id))

    filters = []
    if target_date is not None:
        filters.append(Appointment.date == target_date)
    if doctor_id is not None:
        filters.append(Appointment.doctor_id == doctor_id)
    if status:
        filters.append(func.lower(Appointment.status) == status.lower())
    if search:
        stmt = stmt.join(Patient)
        count_stmt = count_stmt.join(Patient)
        filters.append(Patient.name.ilike(f"%{search}%"))

    for item in filters:
        stmt = stmt.where(item)
        count_stmt = count_stmt.where(item)

    offset = (page - 1) * limit
    result = await db.execute(stmt.limit(limit).offset(offset))
    total = await _scalar(db, count_stmt)
    items = [_appointment_row(appt) for appt in result.scalars().all()]

    return {"items": items, "total": int(total or 0), "page": page, "limit": limit}


@router.get("/notifications")
async def get_admin_notifications(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    notification_type: Optional[str] = Query(None),
):
    stmt = (
        select(Notification)
        .options(selectinload(Notification.patient), selectinload(Notification.appointment))
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    if notification_type:
        stmt = stmt.where(Notification.notification_type == notification_type)
    result = await db.execute(stmt)
    notifications = result.scalars().all()
    return [_notification_row(item) for item in notifications]


@router.get("/ops-alerts")
async def get_admin_ops_alerts(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    severity: Optional[str] = None,
):
    stmt = select(OpsAlert).order_by(OpsAlert.created_at.desc()).limit(limit)
    if severity:
        stmt = stmt.where(func.lower(OpsAlert.severity) == severity.lower())
    result = await db.execute(stmt)
    return [_ops_alert_row(item) for item in result.scalars().all()]


@router.get("/reassignments")
async def get_admin_reassignments(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
):
    stmt = (
        select(OpsAlert)
        .where(OpsAlert.details["appointment_id"].as_string().isnot(None))
        .order_by(OpsAlert.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    alerts = result.scalars().all()

    doctor_ids = set()
    for alert in alerts:
        details = alert.details or {}
        if details.get("original_doctor_id") is not None:
            doctor_ids.add(details.get("original_doctor_id"))
        if details.get("new_doctor_id") is not None:
            doctor_ids.add(details.get("new_doctor_id"))

    doctor_names = {}
    if doctor_ids:
        doctor_result = await db.execute(select(Doctor).where(Doctor.id.in_(doctor_ids)))
        doctor_names = {doctor.id: doctor.name for doctor in doctor_result.scalars().all()}

    return [_reassignment_row(alert, doctor_names) for alert in alerts]


@router.get("/agent-runs")
async def get_agent_runs(
    db: AsyncSession = Depends(get_db),
    agent: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
):
    stmt = select(AgentRun).order_by(AgentRun.started_at.desc()).limit(limit)
    if agent:
        aliases = {
            "booking": "booking_agent",
            "scheduling": "scheduling_agent",
            "ops_monitor": "ops_monitor",
        }
        stmt = stmt.where(AgentRun.agent == aliases.get(agent, agent))
    result = await db.execute(stmt)
    return [_agent_run_row(item) for item in result.scalars().all()]


@router.get("/ml/predictions")
async def get_admin_predictions(
    db: AsyncSession = Depends(get_db),
    model: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    page: int = Query(1, ge=1),
):
    stmt = (
        select(MLPrediction)
        .options(selectinload(MLPrediction.appointment))
        .order_by(MLPrediction.predicted_at.desc())
    )
    if model:
        stmt = stmt.where(MLPrediction.model_name == model)
    result = await db.execute(stmt.limit(limit).offset((page - 1) * limit))
    return [_prediction_row(item) for item in result.scalars().all()]


@router.get("/ml/model-status")
async def get_model_status(name: str, db: AsyncSession = Depends(get_db)):
    stmt = select(MLPrediction).where(MLPrediction.model_name == name)
    result = await db.execute(stmt.order_by(MLPrediction.predicted_at.desc()).limit(1))
    latest = result.scalar_one_or_none()

    count = await _scalar(db, select(func.count(MLPrediction.id)).where(MLPrediction.model_name == name))
    resolved = await _scalar(
        db,
        select(func.count(MLPrediction.id)).where(
            MLPrediction.model_name == name,
            MLPrediction.actual_value.isnot(None),
        ),
    )
    metric = await _prediction_error_metric(db, name)

    return {
        "name": name,
        "version": latest.model_version if latest else "unknown",
        "stage": "Production" if latest else "Not trained",
        "prediction_count": int(count or 0),
        "resolved_count": int(resolved or 0),
        "metric_name": "MAE" if "load" in name else "RMSE",
        "metric_value": metric,
        "last_prediction_at": _iso(latest.predicted_at) if latest else None,
        "features": list((latest.input_features or {}).keys()) if latest else [],
    }


@router.get("/ml/drift-history")
async def get_drift_history(db: AsyncSession = Depends(get_db), limit: int = Query(30, ge=1, le=120)):
    since = datetime.now(timezone.utc) - timedelta(days=limit)
    stmt = (
        select(
            MLPrediction.model_name,
            func.date(MLPrediction.predicted_at).label("day"),
            func.avg(func.abs(MLPrediction.predicted_value - MLPrediction.actual_value)).label("avg_error"),
            func.count(MLPrediction.id).label("samples"),
        )
        .where(MLPrediction.predicted_at >= since, MLPrediction.actual_value.isnot(None))
        .group_by(MLPrediction.model_name, func.date(MLPrediction.predicted_at))
        .order_by(func.date(MLPrediction.predicted_at).desc())
    )
    result = await db.execute(stmt)
    return [
        {
            "model_name": model_name,
            "date": str(day),
            "kl_divergence": round(min(float(avg_error or 0) / 100.0, 1.0), 4),
            "sample_count": int(samples or 0),
            "triggered_retraining": bool(avg_error and avg_error > 10),
        }
        for model_name, day, avg_error, samples in result.all()
    ]


@router.get("/anomaly-history")
async def get_anomaly_history(db: AsyncSession = Depends(get_db), limit: int = Query(48, ge=1, le=500)):
    stmt = select(AnomalyPrediction).order_by(AnomalyPrediction.timestamp.desc()).limit(limit)
    result = await db.execute(stmt)
    return [
        {
            "id": item.id,
            "type": item.type,
            "value": item.value,
            "timestamp": _iso(item.timestamp),
            "metadata": item.metadata_json or {},
            "is_anomaly": bool((item.value or 0) < -0.3),
        }
        for item in result.scalars().all()
    ]


@router.get("/voice-sessions")
async def get_voice_sessions(db: AsyncSession = Depends(get_db), limit: int = Query(20, ge=1, le=200)):
    voice_channels = [
        BookingChannel.VOICE_NOTE,
        BookingChannel.WEBRTC_CALL,
        BookingChannel.TWILIO_CALL,
    ]
    stmt = (
        select(Appointment)
        .options(selectinload(Appointment.patient), selectinload(Appointment.doctor))
        .where(Appointment.booking_channel.in_(voice_channels))
        .order_by(Appointment.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [
        {
            "session_id": appt.id,
            "mode": (appt.booking_channel.value if appt.booking_channel else "voice_note"),
            "language": appt.patient.preferred_lang if appt.patient else "unknown",
            "stt_provider": "Groq Whisper",
            "transcript": appt.complaint or appt.reason or "",
            "agent_steps": None,
            "duration": None,
            "outcome": _enum_value(appt.status),
            "created_at": _iso(appt.created_at),
        }
        for appt in result.scalars().all()
    ]


@router.get("/celery/task-history")
async def get_celery_task_history(task: Optional[str] = None, limit: int = Query(10, ge=1, le=50)):
    try:
        from tasks.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule or {}
    except Exception:
        schedule = {}

    rows = []
    for name, entry in schedule.items():
        if task and task not in name and task not in str(entry.get("task", "")):
            continue
        rows.append(
            {
                "id": name,
                "task": entry.get("task", name),
                "schedule": str(entry.get("schedule", "")),
                "status": "scheduled",
                "last_run_at": None,
                "duration_ms": None,
            }
        )
    return rows[:limit]


@router.get("/mlflow/{mlflow_path:path}")
async def proxy_mlflow_get(mlflow_path: str, request: Request):
    return await _proxy_mlflow("GET", mlflow_path, params=dict(request.query_params))


@router.post("/mlflow/{mlflow_path:path}")
async def proxy_mlflow_post(mlflow_path: str, request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = None
    return await _proxy_mlflow("POST", mlflow_path, json_payload=payload)


@router.get("/ci/runs")
async def get_ci_runs(limit: int = Query(10, ge=1, le=50)):
    repository = os.getenv("GITHUB_REPOSITORY", "syedukkashah/clinic-ai")
    token = os.getenv("GITHUB_TOKEN")
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"https://api.github.com/repos/{repository}/actions/runs"
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            response = await client.get(url, headers=headers, params={"per_page": limit})
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"GitHub Actions unavailable: {exc}") from exc

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    payload = response.json()
    return {
        "repository": repository,
        "source": "github_actions",
        "runs": [_ci_run_row(item) for item in payload.get("workflow_runs", [])],
    }


@router.get("/llm/key-events")
async def get_llm_key_events():
    return llm_router.get_rate_limit_events()


async def _proxy_mlflow(
    method: str,
    mlflow_path: str,
    *,
    params: Optional[dict] = None,
    json_payload: Optional[dict] = None,
):
    if not MLFLOW_BASE_URL.startswith(("http://", "https://")):
        raise HTTPException(
            status_code=503,
            detail=f"MLflow HTTP API unavailable for tracking URI {MLFLOW_BASE_URL}",
        )

    url = f"{MLFLOW_BASE_URL.rstrip('/')}/api/2.0/mlflow/{mlflow_path}"
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            response = await client.request(method, url, params=params, json=json_payload)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"MLflow unavailable: {exc}") from exc

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


async def _scalar(db: AsyncSession, stmt):
    result = await db.execute(stmt)
    return result.scalar()


async def _latest_anomaly_score(db: AsyncSession) -> float:
    result = await db.execute(
        select(AnomalyPrediction.value).order_by(AnomalyPrediction.timestamp.desc()).limit(1)
    )
    value = result.scalar_one_or_none()
    return float(value or 0)


async def _prediction_error_metric(db: AsyncSession, model_name: str) -> Optional[float]:
    result = await db.execute(
        select(MLPrediction.predicted_value, MLPrediction.actual_value).where(
            MLPrediction.model_name == model_name,
            MLPrediction.actual_value.isnot(None),
        )
    )
    pairs = [(float(pred), float(actual)) for pred, actual in result.all()]
    if not pairs:
        return None
    errors = [pred - actual for pred, actual in pairs]
    if "load" in model_name:
        return round(sum(abs(value) for value in errors) / len(errors), 3)
    return round(math.sqrt(sum(value * value for value in errors) / len(errors)), 3)


def _appointment_row(appt: Appointment) -> dict:
    return {
        "id": appt.id,
        "patient_id": appt.patient_id,
        "patient_name": appt.patient.name if appt.patient else None,
        "doctor_id": appt.doctor_id,
        "doctor_name": appt.doctor.name if appt.doctor else None,
        "specialty": appt.specialty or (appt.doctor.specialty if appt.doctor else None),
        "scheduled_at": _iso(appt.scheduled_at),
        "date": appt.date.isoformat() if appt.date else None,
        "time": appt.time,
        "predicted_wait_minutes": appt.predicted_wait_min,
        "actual_wait_minutes": appt.actual_wait_minutes,
        "booking_channel": _enum_value(appt.booking_channel) or "chat",
        "status": _enum_value(appt.status),
        "reason": appt.reason or appt.complaint,
        "created_at": _iso(appt.created_at),
    }


def _notification_row(item: Notification) -> dict:
    message = item.message or ""
    language = item.patient.preferred_lang if item.patient else _detect_language(message)
    recipient = item.patient.name if item.patient else None
    return {
        "id": item.id,
        "type": item.notification_type,
        "recipient": recipient or item.patient_id or "clinic",
        "patient_id": item.patient_id,
        "appointment_id": item.appointment_id,
        "message": message,
        "language": language,
        "triggered_by": "scheduling_agent" if "moved" in message.lower() else "booking_agent",
        "sent_at": _iso(item.created_at),
        "created_at": _iso(item.created_at),
        "mock": bool(item.is_mock),
        "is_mock": bool(item.is_mock),
    }


def _ops_alert_row(item: OpsAlert) -> dict:
    details = item.details or {}
    return {
        "id": item.id,
        "severity": item.severity,
        "message": item.message,
        "title": item.message,
        "triggered_by": details.get("type") or item.agent,
        "steps_taken": details.get("reasoning") or details.get("steps_taken"),
        "created_at": _iso(item.created_at),
        "acknowledged": bool(details.get("acknowledged", False)),
        "channel": item.channel,
        "agent": item.agent,
        "details": details,
    }


def _reassignment_row(item: OpsAlert, doctor_names: dict) -> dict:
    details = item.details or {}
    original_id = details.get("original_doctor_id")
    new_id = details.get("new_doctor_id")
    return {
        "id": item.id,
        "appointment_id": details.get("appointment_id"),
        "from_doctor_id": original_id,
        "from_doctor": doctor_names.get(original_id),
        "to_doctor_id": new_id,
        "to_doctor": doctor_names.get(new_id),
        "reason": details.get("reason") or details.get("trigger") or "Load balancing",
        "predicted_wait_before": details.get("original_predicted_wait"),
        "predicted_wait_after": details.get("new_predicted_wait"),
        "original_start_time": details.get("original_start_time"),
        "new_start_time": details.get("new_start_time"),
        "created_at": _iso(item.created_at),
        "severity": item.severity,
        "message": item.message,
    }


def _ci_run_row(item: dict) -> dict:
    return {
        "id": item.get("id"),
        "run_number": item.get("run_number"),
        "name": item.get("name"),
        "branch": item.get("head_branch"),
        "commit": (item.get("head_sha") or "")[:8],
        "trigger": item.get("event"),
        "status": item.get("status"),
        "conclusion": item.get("conclusion"),
        "started_at": item.get("run_started_at") or item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "url": item.get("html_url"),
    }


def _prediction_row(item: MLPrediction) -> dict:
    actual = item.actual_value
    error = None if actual is None else round(float(item.predicted_value) - float(actual), 3)
    return {
        "id": item.id,
        "model": item.model_name,
        "model_name": item.model_name,
        "version": item.model_version,
        "model_version": item.model_version,
        "appointment_id": item.appointment_id,
        "target_doctor_id": item.target_doctor_id,
        "target_date": item.target_date.isoformat() if item.target_date else None,
        "target_hour": item.target_hour,
        "predicted": item.predicted_value,
        "predicted_value": item.predicted_value,
        "actual": actual,
        "actual_value": actual,
        "error": error,
        "predicted_at": _iso(item.predicted_at),
        "resolved_at": _iso(item.resolved_at),
        "status": "RESOLVED" if actual is not None else "PENDING",
        "input_features": item.input_features,
    }


def _agent_run_row(item: AgentRun) -> dict:
    tool_calls = item.tool_calls or []
    return {
        "id": item.id,
        "run_id": item.id,
        "agent": item.agent,
        "session_id": item.session_id,
        "mode": item.mode,
        "language": item.language,
        "trigger": item.trigger,
        "outcome": item.outcome,
        "steps": tool_calls,
        "tool_calls": tool_calls,
        "steps_count": item.steps_count or len(tool_calls),
        "providers": item.providers_used or [],
        "providers_used": item.providers_used or [],
        "duration_ms": item.duration_ms,
        "summary": item.summary,
        "started_at": _iso(item.started_at),
        "completed_at": _iso(item.completed_at),
    }


def _detect_language(text: str) -> str:
    return "ur" if re.search(r"[\u0600-\u06FF]", text or "") else "en"


def _enum_value(value):
    return getattr(value, "value", value)


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None
