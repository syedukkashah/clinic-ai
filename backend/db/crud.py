"""
db/crud.py — Async data-access layer.

Every route calls functions here instead of writing raw SQL.
All functions accept an AsyncSession and return dicts that match
the Pydantic response schemas exactly.
"""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import Date, func, select, cast, case, text, delete as sa_delete, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import (
    Appointment,
    AppointmentStatus,
    BookingChannel,
    DailyLoad,
    Doctor,
    MLPrediction,
    Notification,
    OpsAlert,
    Patient,
    Slot,
    UrgencyLevel,
)

# ── Colour palette for doctor avatars (cycled by id) ─────────────────────────
_AVATAR_COLORS = [
    "from-blue-500 to-cyan-500",
    "from-violet-500 to-fuchsia-500",
    "from-emerald-500 to-teal-500",
    "from-amber-500 to-orange-500",
    "from-rose-500 to-pink-500",
    "from-indigo-500 to-blue-500",
    "from-lime-500 to-green-500",
    "from-yellow-500 to-amber-500",
    "from-cyan-500 to-sky-500",
    "from-fuchsia-500 to-purple-500",
    "from-teal-500 to-emerald-500",
]

DEFAULT_CAPACITY = 22


# ═══════════════════════════════════════════════════════════════════════════════
#  DOCTORS
# ═══════════════════════════════════════════════════════════════════════════════

async def get_doctors(db: AsyncSession) -> List[Dict[str, Any]]:
    """Return all doctors with dynamically computed dashboard fields."""
    today = date.today()

    # Sub-query: count today's appointments per doctor
    appt_counts = (
        select(
            Appointment.doctor_id,
            func.count(Appointment.id).label("appt_count"),
        )
        .where(Appointment.date == today)
        .group_by(Appointment.doctor_id)
        .subquery()
    )

    stmt = (
        select(Doctor, appt_counts.c.appt_count)
        .outerjoin(appt_counts, Doctor.id == appt_counts.c.doctor_id)
        .order_by(Doctor.id)
    )
    result = await db.execute(stmt)
    rows = result.all()

    out: List[Dict[str, Any]] = []
    for doctor, appt_count in rows:
        count = appt_count or 0
        if not doctor.is_available:
            status = "off"
        elif count >= DEFAULT_CAPACITY:
            status = "overloaded"
        elif count >= DEFAULT_CAPACITY * 0.6:
            status = "busy"
        else:
            status = "available"

        out.append({
            "id": doctor.id,
            "name": doctor.name,
            "specialty": doctor.specialty,
            "avatarColor": _AVATAR_COLORS[(doctor.id - 1) % len(_AVATAR_COLORS)],
            "appointmentsToday": count,
            "capacity": DEFAULT_CAPACITY,
            "status": status,
            "avgConsultMin": int(doctor.avg_consult_duration or 10),
        })
    return out


async def get_doctor(db: AsyncSession, doctor_id: int) -> Optional[Dict[str, Any]]:
    """Return a single doctor by ID."""
    stmt = select(Doctor).where(Doctor.id == doctor_id)
    result = await db.execute(stmt)
    doctor = result.scalar_one_or_none()
    if doctor is None:
        return None

    # Count today's appointments
    today = date.today()
    count_stmt = (
        select(func.count(Appointment.id))
        .where(Appointment.doctor_id == doctor_id, Appointment.date == today)
    )
    count_result = await db.execute(count_stmt)
    count = count_result.scalar() or 0

    if not doctor.is_available:
        status = "off"
    elif count >= DEFAULT_CAPACITY:
        status = "overloaded"
    elif count >= DEFAULT_CAPACITY * 0.6:
        status = "busy"
    else:
        status = "available"

    return {
        "id": doctor.id,
        "name": doctor.name,
        "specialty": doctor.specialty,
        "avatarColor": _AVATAR_COLORS[(doctor.id - 1) % len(_AVATAR_COLORS)],
        "appointmentsToday": count,
        "capacity": DEFAULT_CAPACITY,
        "status": status,
        "avgConsultMin": int(doctor.avg_consult_duration or 10),
    }


async def get_doctor_availability(db: AsyncSession, doctor_id: int) -> Dict[str, Any]:
    """Return available slots for a doctor."""
    stmt = (
        select(Slot)
        .where(Slot.doctor_id == doctor_id, Slot.is_available == True)
        .order_by(Slot.start_time)
        .limit(20)
    )
    result = await db.execute(stmt)
    slots = result.scalars().all()

    if slots:
        available = [s.start_time.strftime("%H:%M") for s in slots]
    else:
        # Fallback: generate default time slots when no slots exist in DB
        available = ["08:00", "08:30", "09:00", "09:30", "10:00",
                     "10:30", "14:00", "14:30", "15:00", "15:30", "16:00"]

    return {"doctorId": doctor_id, "availableSlots": available}


# ═══════════════════════════════════════════════════════════════════════════════
#  APPOINTMENTS
# ═══════════════════════════════════════════════════════════════════════════════

def _appointment_to_dict(appt: Appointment, patient_name: str, doctor_name: str) -> Dict[str, Any]:
    """Convert an Appointment ORM object to schema-compatible dict."""
    return {
        "id": appt.id,
        "patientName": patient_name,
        "patientId": appt.patient_id,
        "doctorId": appt.doctor_id,
        "doctorName": doctor_name,
        "time": appt.time or (appt.scheduled_at.strftime("%H:%M") if appt.scheduled_at else "00:00"),
        "date": appt.date.isoformat() if appt.date else (appt.scheduled_at.date().isoformat() if appt.scheduled_at else date.today().isoformat()),
        "status": appt.status,
        "predictedWaitMin": appt.predicted_wait_min or 0,
        "reason": appt.reason or appt.complaint or "Consultation",
        "slotId": str(appt.slot_id) if appt.slot_id else None,
        "urgency": appt.urgency.value.lower() if appt.urgency else "routine",
    }


async def get_appointments(
    db: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
    doctor_id: Optional[int] = None,
    status: Optional[str] = None,
    target_date: Optional[date] = None,
    search: Optional[str] = None,
) -> Dict[str, Any]:
    """Return appointments with patient and doctor names joined + total count."""
    # 1. Total count
    count_stmt = select(func.count(Appointment.id)).join(Patient, Appointment.patient_id == Patient.id)
    if doctor_id is not None:
        count_stmt = count_stmt.where(Appointment.doctor_id == doctor_id)
    if status is not None:
        count_stmt = count_stmt.where(Appointment.status == status)
    if target_date is not None:
        count_stmt = count_stmt.where(Appointment.date == target_date)
    if search:
        count_stmt = count_stmt.where(Patient.name.ilike(f"%{search}%"))
    
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    # 2. Results
    stmt = (
        select(Appointment, Patient.name, Doctor.name)
        .join(Patient, Appointment.patient_id == Patient.id)
        .join(Doctor, Appointment.doctor_id == Doctor.id)
        .order_by(Appointment.scheduled_at.desc())
    )

    if doctor_id is not None:
        stmt = stmt.where(Appointment.doctor_id == doctor_id)
    if status is not None:
        stmt = stmt.where(Appointment.status == status)
    if target_date is not None:
        stmt = stmt.where(Appointment.date == target_date)
    if search:
        stmt = stmt.where(Patient.name.ilike(f"%{search}%"))

    stmt = stmt.limit(limit).offset(offset)
    logger.info("Executing appointments query: %s", stmt)
    result = await db.execute(stmt)
    rows = result.all()

    items = [_appointment_to_dict(appt, pname, dname) for appt, pname, dname in rows]
    
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset
    }


async def get_appointment_by_id(db: AsyncSession, appointment_id: str) -> Optional[Dict[str, Any]]:
    """Return a single appointment."""
    stmt = (
        select(Appointment, Patient.name, Doctor.name)
        .join(Patient, Appointment.patient_id == Patient.id)
        .join(Doctor, Appointment.doctor_id == Doctor.id)
        .where(Appointment.id == appointment_id)
    )
    result = await db.execute(stmt)
    row = result.one_or_none()
    if row is None:
        return None
    appt, pname, dname = row
    return _appointment_to_dict(appt, pname, dname)


async def create_appointment(db: AsyncSession, data: Dict[str, Any]) -> Dict[str, Any]:
    """Insert a new appointment and return it."""
    import time as _time

    appt_id = data.get("id") or f"apt-{int(_time.time() * 1000)}"

    urgency_val = (data.get("urgency") or "routine").upper()
    try:
        urgency_enum = UrgencyLevel[urgency_val]
    except KeyError:
        urgency_enum = UrgencyLevel.ROUTINE

    appt = Appointment(
        id=appt_id,
        patient_id=data["patientId"],
        doctor_id=data["doctorId"],
        scheduled_at=datetime.now(timezone.utc),
        date=date.fromisoformat(data.get("date", date.today().isoformat())),
        time=data.get("time"),
        status=AppointmentStatus.CONFIRMED,
        urgency=urgency_enum,
        reason=data.get("reason"),
        slot_id=int(data["slotId"]) if data.get("slotId") else None,
        predicted_wait_min=data.get("predictedWaitMin", 0),
    )
    db.add(appt)
    await db.flush()

    return {
        "id": appt.id,
        "patientName": data.get("patientName", ""),
        "patientId": appt.patient_id,
        "doctorId": appt.doctor_id,
        "doctorName": data.get("doctorName", ""),
        "time": appt.time or "00:00",
        "date": appt.date.isoformat() if appt.date else date.today().isoformat(),
        "status": appt.status,
        "predictedWaitMin": appt.predicted_wait_min or 0,
        "reason": appt.reason or "Consultation",
        "slotId": str(appt.slot_id) if appt.slot_id else None,
        "urgency": appt.urgency.value.lower() if appt.urgency else "routine",
    }


async def update_appointment(db: AsyncSession, appointment_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update an existing appointment. Returns updated dict or None."""
    stmt = select(Appointment).where(Appointment.id == appointment_id)
    result = await db.execute(stmt)
    appt = result.scalar_one_or_none()
    if appt is None:
        return None

    # Map schema field names → ORM column names
    field_map = {
        "status": "status",
        "predictedWaitMin": "predicted_wait_min",
        "reason": "reason",
        "time": "time",
        "date": "date",
        "doctorId": "doctor_id",
        "urgency": "urgency",
        "slotId": "slot_id",
    }

    for schema_key, orm_key in field_map.items():
        if schema_key in patch:
            val = patch[schema_key]
            if schema_key == "urgency" and val is not None:
                try:
                    val = UrgencyLevel[val.upper()]
                except (KeyError, AttributeError):
                    val = UrgencyLevel.ROUTINE
            if schema_key == "date" and isinstance(val, str):
                val = date.fromisoformat(val)
            if schema_key == "slotId" and val is not None:
                val = int(val)
            setattr(appt, orm_key, val)

    await db.flush()
    return await get_appointment_by_id(db, appointment_id)


async def delete_appointment(db: AsyncSession, appointment_id: str) -> bool:
    """Delete an appointment. Returns True if deleted."""
    stmt = sa_delete(Appointment).where(Appointment.id == appointment_id)
    result = await db.execute(stmt)
    return result.rowcount > 0


# ═══════════════════════════════════════════════════════════════════════════════
#  PATIENTS
# ═══════════════════════════════════════════════════════════════════════════════

async def get_patients(db: AsyncSession, *, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    stmt = select(Patient).order_by(Patient.name).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return [
        {"id": p.id, "name": p.name, "email": p.email, "phone": p.phone}
        for p in result.scalars().all()
    ]


# ═══════════════════════════════════════════════════════════════════════════════
#  ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════════

async def get_overview_stats(db: AsyncSession) -> Dict[str, Any]:
    """Dashboard overview: total today, in queue, avg wait, health score."""
    today = date.today()

    total_q = select(func.count(Appointment.id)).where(Appointment.date == today)
    queue_q = select(func.count(Appointment.id)).where(
        Appointment.date == today,
        Appointment.status.in_([AppointmentStatus.CONFIRMED, AppointmentStatus.WAITING]),
    )
    avg_wait_q = select(func.coalesce(func.avg(Appointment.predicted_wait_min), 0)).where(
        Appointment.date == today,
        Appointment.status.in_([AppointmentStatus.CONFIRMED, AppointmentStatus.WAITING]),
    )

    total = (await db.execute(total_q)).scalar() or 0
    in_queue = (await db.execute(queue_q)).scalar() or 0
    avg_wait = int((await db.execute(avg_wait_q)).scalar() or 0)
    health = max(20, min(100, 100 - int(avg_wait * 1.2)))

    return {"totalToday": total, "inQueue": in_queue, "avgWait": avg_wait, "health": health}


async def get_wait_series(db: AsyncSession) -> List[Dict[str, Any]]:
    """Hourly average wait times for today from actual data."""
    today = date.today()

    stmt = (
        select(
            func.extract("hour", Appointment.scheduled_at).label("hour"),
            func.coalesce(func.avg(Appointment.actual_wait_minutes), func.avg(Appointment.predicted_wait_min)).label("wait"),
        )
        .where(Appointment.date == today)
        .group_by(func.extract("hour", Appointment.scheduled_at))
        .order_by(func.extract("hour", Appointment.scheduled_at))
    )
    result = await db.execute(stmt)
    rows = result.all()

    if rows:
        return [
            {"time": f"{int(h):02d}:00", "wait": int(w or 0), "threshold": 30}
            for h, w in rows
        ]

    # Fallback: generate reasonable defaults for hours 8-19
    return [
        {"time": f"{h:02d}:00", "wait": max(5, int(12 + (i / 2) + ((i % 3) * 3))), "threshold": 30}
        for i, h in enumerate(range(8, 20))
    ]


async def get_load_forecast(db: AsyncSession) -> List[Dict[str, Any]]:
    """Hourly patient load: actual counts + predicted from daily_load."""
    today = date.today()

    # Actual counts per hour (from appointments)
    actual_stmt = (
        select(
            func.extract("hour", Appointment.scheduled_at).label("hour"),
            func.count(Appointment.id).label("cnt"),
        )
        .where(Appointment.date == today)
        .group_by(func.extract("hour", Appointment.scheduled_at))
    )
    actual_result = await db.execute(actual_stmt)
    actual_map = {int(h): cnt for h, cnt in actual_result.all()}

    # Predicted from daily_load (latest data available)
    pred_stmt = (
        select(DailyLoad.hour_of_day, func.avg(DailyLoad.patient_count).label("avg_load"))
        .where(DailyLoad.scheduled_date == today)
        .group_by(DailyLoad.hour_of_day)
        .order_by(DailyLoad.hour_of_day)
    )
    pred_result = await db.execute(pred_stmt)
    pred_map = {h: int(avg) for h, avg in pred_result.all()}

    out: List[Dict[str, Any]] = []
    for h in range(8, 20):
        actual = actual_map.get(h)
        predicted = pred_map.get(h, int(22 + (h % 4) * 3))
        out.append({"hour": f"{h:02d}:00", "actual": actual, "predicted": predicted})
    return out


# ═══════════════════════════════════════════════════════════════════════════════
#  ML PREDICTIONS
# ═══════════════════════════════════════════════════════════════════════════════

async def create_ml_prediction(db: AsyncSession, data: Dict[str, Any]) -> MLPrediction:
    """Insert a new ML prediction row."""
    pred = MLPrediction(
        model_name=data["model_name"],
        model_version=data["model_version"],
        appointment_id=data.get("appointment_id"),
        target_doctor_id=data.get("target_doctor_id"),
        target_date=data.get("target_date"),
        target_hour=data.get("target_hour"),
        input_features=data["input_features"],
        predicted_value=data["predicted_value"],
        actual_value=data.get("actual_value"),
    )
    db.add(pred)
    await db.flush()
    return pred


async def get_daily_load(
    db: AsyncSession,
    *,
    doctor_id: Optional[int] = None,
    target_date: Optional[date] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Read daily_load rows for ML features."""
    stmt = select(DailyLoad).order_by(DailyLoad.scheduled_date.desc(), DailyLoad.hour_of_day)

    if doctor_id is not None:
        stmt = stmt.where(DailyLoad.doctor_id == doctor_id)
    if target_date is not None:
        stmt = stmt.where(DailyLoad.scheduled_date == target_date)

    stmt = stmt.limit(limit)
    result = await db.execute(stmt)

    return [
        {
            "id": dl.id,
            "doctor_id": dl.doctor_id,
            "specialty": dl.specialty,
            "scheduled_date": dl.scheduled_date.isoformat(),
            "hour_of_day": dl.hour_of_day,
            "day_of_week": dl.day_of_week,
            "week_of_year": dl.week_of_year,
            "is_holiday": dl.is_holiday,
            "is_day_after_holiday": dl.is_day_after_holiday,
            "is_ramadan": dl.is_ramadan,
            "season": dl.season,
            "patient_count": dl.patient_count,
            "lag_1w": dl.lag_1w,
            "lag_2w": dl.lag_2w,
            "roll_4w_avg": dl.roll_4w_avg,
        }
        for dl in result.scalars().all()
    ]


# ═══════════════════════════════════════════════════════════════════════════════
#  HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════════════════

async def check_db(db: AsyncSession) -> Dict[str, Any]:
    """Run a simple query to verify DB connectivity."""
    from sqlalchemy import text
    result = await db.execute(text("SELECT 1"))
    result.scalar()

    # Get table counts for diagnostics
    tables = ["doctors", "patients", "appointments", "daily_load", "ml_predictions"]
    counts = {}
    for t in tables:
        r = await db.execute(text(f"SELECT COUNT(*) FROM {t}"))
        counts[t] = r.scalar()

    return {"status": "connected", "tables": counts}


# ═══════════════════════════════════════════════════════════════════════════════
#  OPS ALERTS & ACTIVITY
# ═══════════════════════════════════════════════════════════════════════════════

async def get_ops_alerts(
        db: AsyncSession,
        limit: int = 50,
        severity: Optional[str] = None,
    ) -> List[OpsAlert]:
        stmt = select(OpsAlert).order_by(OpsAlert.created_at.desc()).limit(limit)
        if severity:
            stmt = stmt.where(OpsAlert.severity == severity.upper())
        result = await db.execute(stmt)
        return result.scalars().all()


async def create_ops_alert(db: AsyncSession, data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new ops alert."""
    details = {
        "reasoning": data.get("reasoning", ""),
        "type": data.get("type", "surge"),
        "trace": data.get("trace", []),
        "recommendedActions": data.get("recommendedActions", []),
        "acknowledged": False,
    }
    alert = OpsAlert(
        message=data.get("title", "Alert"),
        severity=data.get("severity", "High"),
        details=details,
    )
    db.add(alert)
    await db.flush()
    return {
        "id": f"alt-{alert.id}",
        "severity": alert.severity,
        "title": alert.message,
        "reasoning": details["reasoning"],
        "timestamp": alert.created_at.isoformat() if alert.created_at else "just now",
        "type": details["type"],
        "trace": details["trace"],
        "recommendedActions": details["recommendedActions"],
        "acknowledged": details["acknowledged"],
    }


async def acknowledge_ops_alert(db: AsyncSession, alert_id: str) -> bool:
    """Acknowledge an ops alert."""
    try:
        db_id = int(alert_id.replace("alt-", ""))
    except ValueError:
        return False

    stmt = select(OpsAlert).where(OpsAlert.id == db_id)
    result = await db.execute(stmt)
    alert = result.scalar_one_or_none()
    if not alert:
        return False

    details = dict(alert.details or {})
    details["acknowledged"] = True
    alert.details = details
    await db.flush()
    return True


async def get_activity_feed(db: AsyncSession) -> List[Dict[str, Any]]:
    """Generate activity feed from recent appointments and alerts."""
    import time
    
    # Fetch recent appointments
    appt_stmt = (
        select(Appointment, Patient.name, Doctor.name)
        .join(Patient, Appointment.patient_id == Patient.id)
        .join(Doctor, Appointment.doctor_id == Doctor.id)
        .order_by(Appointment.created_at.desc())
        .limit(10)
    )
    appt_result = await db.execute(appt_stmt)
    appts = appt_result.all()

    activities = []
    for appt, pname, dname in appts:
        timestamp_ms = int(appt.created_at.timestamp() * 1000) if appt.created_at else int(time.time() * 1000)
        
        if appt.status == AppointmentStatus.CANCELLED:
            act_type = "cancel"
            text = f"Cancellation — {pname} (Dr. {dname})"
        elif appt.booking_channel == BookingChannel.CHAT:
            act_type = "ai"
            text = f"AI agent confirmed appointment for {pname}"
        elif appt.booking_channel in [BookingChannel.VOICE_NOTE, BookingChannel.WEBRTC_CALL, BookingChannel.TWILIO_CALL]:
            act_type = "voice"
            text = f"Voice booking completed — {pname}"
        else:
            act_type = "booking"
            text = f"New booking — {pname} with Dr. {dname}"
            
        activities.append({
            "id": f"act-appt-{appt.id}",
            "type": act_type,
            "text": text,
            "time": "recent",
            "at": timestamp_ms
        })
        
    activities.sort(key=lambda x: x["at"], reverse=True)
    return activities[:10]


async def get_dynamic_metrics(db: AsyncSession) -> Dict[str, Any]:
    """Calculate real-time operational metrics."""
    import time
    from datetime import timedelta
    
    thirty_mins_ago = datetime.now(timezone.utc) - timedelta(minutes=30)
    
    # Count bookings in last 30m
    count_stmt = select(func.count(Appointment.id)).where(Appointment.created_at >= thirty_mins_ago)
    count_result = await db.execute(count_stmt)
    booking_volume = count_result.scalar() or 0

    return {
        "bookingVolume30m": booking_volume,
        "p95LatencyMs": 1200, # Mocked
        "apiErrorRatePct": 1.6, # Mocked
        "anomalyScore": 0.32, # Mocked
        "waitModelDriftKl": 0.06, # Mocked
        "keyPoolAvailable": {"gemini": 11, "groq": 18, "together": 7, "openrouter": 4},
    }

async def get_booking_counts_bucketed(
    db: AsyncSession, since: datetime, bucket_minutes: int = 5
) -> List:
    result = await db.execute(
        text("""
            SELECT date_trunc('hour', created_at) +
                   INTERVAL '1 minute' * :bucket * FLOOR(
                       EXTRACT(MINUTE FROM created_at) / :bucket
                   ) AS bucket,
                   COUNT(*) AS count
            FROM appointments
            WHERE created_at >= :since
            GROUP BY bucket
            ORDER BY bucket
        """),
        {"since": since, "bucket": bucket_minutes}
    )
    return result.fetchall()


async def create_slots_for_doctor(
    db: AsyncSession, doctor_id: int, date: datetime,
    specialty: str, count: int
) -> List[Slot]:
    slots = []
    for i in range(count):
        slot = Slot(
            doctor_id=doctor_id,
            specialty=specialty,
            start_time=date,
            is_available=True
        )
        db.add(slot)
        slots.append(slot)
    await db.commit()
    return slots


async def get_recent_predictions(
    db: AsyncSession, model_name: str,
    since: datetime, resolved_only: bool = True
) -> List[MLPrediction]:
    query = select(MLPrediction).where(
        MLPrediction.model_name == model_name,
        MLPrediction.predicted_at >= since
    )
    if resolved_only:
        query = query.where(MLPrediction.actual_value.isnot(None))
    result = await db.execute(query)
    return result.scalars().all()


async def get_baseline_distribution(
    db: AsyncSession, model_name: str
) -> Optional[List[float]]:
    result = await db.execute(
        select(MLPrediction.predicted_value).where(
            MLPrediction.model_name == model_name,
            MLPrediction.actual_value.isnot(None)
        ).limit(1000)
    )
    rows = result.scalars().all()
    return [float(r) for r in rows] if rows else None


async def count_appointments_since(
    db: AsyncSession, since: datetime
) -> int:
    result = await db.execute(
        select(func.count()).where(Appointment.created_at >= since)
    )
    return result.scalar() or 0


async def count_cancellations_since(
    db: AsyncSession, since: datetime
) -> int:
    result = await db.execute(
        select(func.count()).where(
            Appointment.created_at >= since,
            Appointment.status == "CANCELLED"
        )
    )
    return result.scalar() or 0


async def get_avg_predicted_wait(
    db: AsyncSession, since: datetime
) -> Optional[float]:
    result = await db.execute(
        select(func.avg(MLPrediction.predicted_value)).where(
            MLPrediction.model_name == "wait_time_model",
            MLPrediction.predicted_at >= since
        )
    )
    return result.scalar()


async def create_notification(
    db: AsyncSession, recipient_id: int, recipient_type: str,
    message: str, lang: str = "en"
) -> Notification:
    notif = Notification(
        recipient_id=recipient_id,
        recipient_type=recipient_type,
        message=message,
        lang=lang
    )
    db.add(notif)
    await db.commit()
    await db.refresh(notif)
    return notif
