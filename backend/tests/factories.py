from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from uuid import uuid4

from db.models import (
    Appointment,
    AppointmentStatus,
    Doctor,
    OpsAlert,
    Patient,
    Slot,
    UrgencyLevel,
)


async def seed_clinic_data(db_session) -> dict:
    """
    Insert a minimum viable clinic dataset and return stable IDs.

    The project currently uses a synchronous SQLAlchemy session in tests, so
    this async helper intentionally performs sync session operations while
    keeping the async signature expected by pytest fixtures.
    """
    suffix = uuid4().hex[:8]
    doctors = {
        "general": Doctor(
            name=f"Dr. Ahmed Raza {suffix}",
            specialty="general",
            is_available=True,
            avg_consult_duration=12.0,
        ),
        "cardiology": Doctor(
            name=f"Dr. Nadia Hussain {suffix}",
            specialty="cardiology",
            is_available=True,
            avg_consult_duration=18.0,
        ),
        "pediatrics": Doctor(
            name=f"Dr. Ayesha Khan {suffix}",
            specialty="pediatrics",
            is_available=True,
            avg_consult_duration=15.0,
        ),
    }
    db_session.add_all(doctors.values())
    db_session.flush()

    slot_date = date.today()
    if datetime.now().hour >= 9:
        slot_date = slot_date + timedelta(days=1)

    slot_ids: dict[int, list[int]] = {}
    for doctor in doctors.values():
        slot_ids[doctor.id] = []
        for hour in (9, 10, 11, 14, 15):
            slot = Slot(
                doctor_id=doctor.id,
                start_time=datetime.combine(
                    slot_date,
                    time(hour=hour),
                    tzinfo=timezone.utc,
                ),
                is_available=True,
            )
            db_session.add(slot)
            db_session.flush()
            slot_ids[doctor.id].append(slot.id)

    patients = [
        Patient(
            id=f"pat-{suffix}-1",
            name="Test Patient One",
            email=f"patient-one-{suffix}@example.test",
            phone="03000000001",
            preferred_lang="en",
        ),
        Patient(
            id=f"pat-{suffix}-2",
            name="Test Patient Two",
            email=f"patient-two-{suffix}@example.test",
            phone="03000000002",
            preferred_lang="ur",
        ),
    ]
    db_session.add_all(patients)
    db_session.commit()

    return {
        "doctor_ids": {specialty: doctor.id for specialty, doctor in doctors.items()},
        "slot_ids": slot_ids,
        "patient_ids": [patient.id for patient in patients],
    }


async def create_confirmed_appointment(db_session, patient_id, slot_id) -> str:
    """Create and return an appointment ID for a confirmed appointment."""
    slot = db_session.get(Slot, slot_id)
    if slot is None:
        raise ValueError(f"Slot {slot_id} does not exist")

    appointment = Appointment(
        id=f"apt-{uuid4().hex[:10]}",
        patient_id=patient_id,
        doctor_id=slot.doctor_id,
        slot_id=slot.id,
        scheduled_at=slot.start_time,
        date=slot.start_time.date(),
        time=slot.start_time.strftime("%H:%M"),
        status=AppointmentStatus.CONFIRMED,
        urgency=UrgencyLevel.ROUTINE,
        predicted_wait_min=15,
    )
    slot.is_available = False
    db_session.add(appointment)
    db_session.commit()
    return appointment.id


async def create_ops_alert(db_session, severity: str = "warning", message: str = "Test alert") -> int:
    """Create a test ops alert and return its ID."""
    alert = OpsAlert(
        severity=severity,
        message=message,
        channel="admin",
        agent="ops_monitor",
        details={"reasoning": message, "type": "surge", "acknowledged": False},
    )
    db_session.add(alert)
    db_session.commit()
    return alert.id
