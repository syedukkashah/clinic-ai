from __future__ import annotations

import random
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.session import get_db
from schemas import schemas

router = APIRouter()

MOCK_DOCTORS = [
    {
        "id": "doc-1",
        "name": "Dr. Sarah Chen",
        "specialty": "General Practice",
        "avatarColor": "from-blue-500 to-cyan-500",
        "appointmentsToday": 14,
        "capacity": 22,
        "status": "busy",
        "avgConsultMin": 14,
    },
    {
        "id": "doc-2",
        "name": "Dr. Michael Ross",
        "specialty": "Pediatrics",
        "avatarColor": "from-violet-500 to-fuchsia-500",
        "appointmentsToday": 9,
        "capacity": 22,
        "status": "available",
        "avgConsultMin": 12,
    },
    {
        "id": "doc-3",
        "name": "Dr. Elena Rodriguez",
        "specialty": "Internal Medicine",
        "avatarColor": "from-emerald-500 to-teal-500",
        "appointmentsToday": 24,
        "capacity": 22,
        "status": "overloaded",
        "avgConsultMin": 16,
    },
    {
        "id": "doc-4",
        "name": "Dr. Omar Siddiqui",
        "specialty": "Cardiology",
        "avatarColor": "from-amber-500 to-orange-500",
        "appointmentsToday": 3,
        "capacity": 22,
        "status": "off",
        "avgConsultMin": 10,
    },
]


@router.get("/", response_model=List[schemas.Doctor])
def get_doctors(db: Session = Depends(get_db)):
    return MOCK_DOCTORS


@router.get("/{id}/availability")
def get_doctor_availability(id: str, db: Session = Depends(get_db)):
    base = ["08:00", "08:30", "09:00", "09:30", "10:00", "10:30", "14:00", "14:30", "15:00", "15:30", "16:00"]
    slots = sorted(random.sample(base, k=min(6, len(base))))
    return {"doctorId": id, "availableSlots": slots}
