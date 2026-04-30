from __future__ import annotations

import random
import time
from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.session import get_db
from db.models import AppointmentStatus
from schemas import schemas

router = APIRouter()

_TODAY = date.today().isoformat()
_FIRST = ["Ayesha", "Imran", "Sara", "Bilal", "Hina", "Usman", "Maria", "Ahmed", "Zara", "Faisal", "Noor", "Hassan", "Fatima", "Ali"]
_LAST = ["Khan", "Malik", "Ahmed", "Siddiqui", "Raza", "Hussain", "Iqbal", "Sheikh", "Qureshi", "Akhtar"]
_REASONS = ["Follow-up", "Consultation", "Annual checkup", "Lab review", "Vaccination", "Urgent care", "Prescription refill"]
_STATUSES = [
    AppointmentStatus.CONFIRMED,
    AppointmentStatus.WAITING,
    AppointmentStatus.IN_PROGRESS,
    AppointmentStatus.COMPLETED,
    AppointmentStatus.CANCELLED,
]


def _rand_name() -> str:
    return f"{random.choice(_FIRST)} {random.choice(_LAST)}"


def _seed_appointments() -> List[schemas.Appointment]:
    out: List[schemas.Appointment] = []
    for i in range(30):
        hour = 8 + random.randint(0, 10)
        minute = random.choice([0, 15, 30, 45])
        out.append(
            schemas.Appointment(
                id=f"apt-{i + 1}",
                patientName=_rand_name(),
                patientId=f"pat-{1000 + i}",
                doctorId=f"doc-{1 + (i % 6)}",
                doctorName=f"Dr. {_rand_name()}",
                time=f"{hour:02d}:{minute:02d}",
                date=_TODAY,
                status=random.choice(_STATUSES),
                predictedWaitMin=random.randint(0, 55),
                reason=random.choice(_REASONS),
                urgency=random.choice(["low", "medium", "high"]),
            )
        )
    return out


MOCK_APPOINTMENTS: List[schemas.Appointment] = _seed_appointments()


@router.get("/", response_model=List[schemas.Appointment])
def get_appointments(db: Session = Depends(get_db)):
    return MOCK_APPOINTMENTS


@router.post("/", response_model=schemas.Appointment)
def create_appointment(appointment: schemas.AppointmentCreate, db: Session = Depends(get_db)):
    now = int(time.time() * 1000)
    created = schemas.Appointment(
        id=f"apt-{now}",
        patientName=appointment.patientName,
        patientId=appointment.patientId,
        doctorId=appointment.doctorId,
        doctorName=appointment.doctorName,
        time=appointment.time,
        date=appointment.date,
        status=AppointmentStatus.CONFIRMED,
        predictedWaitMin=random.randint(0, 40),
        reason=appointment.reason,
        slotId=appointment.slotId,
        urgency=appointment.urgency,
    )
    MOCK_APPOINTMENTS.insert(0, created)
    return created


@router.put("/{id}", response_model=schemas.Appointment)
def update_appointment(id: str, appointment_update: schemas.AppointmentUpdate, db: Session = Depends(get_db)):
    for i, apt in enumerate(MOCK_APPOINTMENTS):
        if apt.id == id:
            patch = appointment_update.model_dump(exclude_unset=True)
            updated_apt = apt.model_copy(update=patch)
            MOCK_APPOINTMENTS[i] = updated_apt
            return updated_apt
    raise HTTPException(status_code=404, detail="Appointment not found")


@router.delete("/{id}")
def delete_appointment(id: str, db: Session = Depends(get_db)):
    global MOCK_APPOINTMENTS
    MOCK_APPOINTMENTS = [apt for apt in MOCK_APPOINTMENTS if apt.id != id]
    return {"message": "Deleted successfully"}
