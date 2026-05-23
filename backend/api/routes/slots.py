from __future__ import annotations

from datetime import date, datetime, time as dt_time, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import Appointment, Slot
from db.session import get_db

router = APIRouter()


@router.get("")
async def get_slots(
    db: AsyncSession = Depends(get_db),
    doctor_id: Optional[int] = Query(None),
    target_date: Optional[date] = Query(None, alias="date"),
    limit: int = Query(100, ge=1, le=500),
):
    stmt = (
        select(Slot)
        .options(
            selectinload(Slot.doctor),
            selectinload(Slot.appointment).selectinload(Appointment.patient),
        )
        .order_by(Slot.start_time.asc())
        .limit(limit)
    )
    if doctor_id is not None:
        stmt = stmt.where(Slot.doctor_id == doctor_id)
    if target_date is not None:
        start = datetime.combine(target_date, dt_time.min)
        end = start + timedelta(days=1)
        stmt = stmt.where(Slot.start_time >= start, Slot.start_time < end)

    result = await db.execute(stmt)
    rows = [_slot_row(slot) for slot in result.scalars().all()]
    return {"items": rows, "total": len(rows), "doctor_id": doctor_id, "date": target_date.isoformat() if target_date else None}


def _slot_row(slot: Slot) -> dict:
    appointment = slot.appointment
    return {
        "id": slot.id,
        "slot_id": slot.id,
        "doctor_id": slot.doctor_id,
        "doctor_name": slot.doctor.name if slot.doctor else None,
        "start_time": slot.start_time.isoformat() if slot.start_time else None,
        "date": slot.start_time.date().isoformat() if slot.start_time else None,
        "time": slot.start_time.strftime("%H:%M") if slot.start_time else None,
        "is_available": bool(slot.is_available and appointment is None),
        "status": "booked" if appointment else "available",
        "appointment_id": appointment.id if appointment else None,
        "patient_id": appointment.patient_id if appointment else None,
        "patient_name": appointment.patient.name if appointment and appointment.patient else None,
        "predicted_wait_minutes": appointment.predicted_wait_min if appointment else None,
        "actual_wait_minutes": appointment.actual_wait_minutes if appointment else None,
    }
