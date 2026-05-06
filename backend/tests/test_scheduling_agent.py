import pytest
import asyncio
from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock

from sqlalchemy.orm import Session
from backend.services.scheduling_agent import run_proactive_scheduling
from backend.db.models import Doctor, Patient, Appointment, Notification, OpsAlert, AppointmentStatus

@pytest.mark.asyncio
async def test_scheduling_agent_reassigns_when_overloaded(db_session: Session, mocker):
    """
    Integration test for the scheduling agent.
    - Mocks the ML service to simulate an overloaded doctor.
    - Verifies that an appointment is reassigned.
    - Verifies that a notification and an ops alert are created.
    """
    # 1. Mock the ML Service Client
    mock_ml_client = mocker.patch(
        'backend.services.scheduling_agent.ml_service_client',
        new_callable=AsyncMock
    )

    # Mock patient load to return an "overloaded" forecast
    mock_ml_client.get_patient_load.return_value = {
        "forecast": {"10": 5, "11": 10},
        "peak_hour": 11,
        "peak_hour_patients": 10, # This is > 8, so it will trigger the overload logic
        "model_version": "patient_load_model_v_test"
    }

    # Mock wait time to return a high value first, then a low value
    mock_ml_client.get_wait_time.side_effect = [
        {
            "predicted_wait_minutes": 50.0, # High wait time, triggers search for alternative
            "model_version": "wait_time_model_v_test"
        },
        {
            "predicted_wait_minutes": 15.0, # Low wait time, confirms the new slot is good
            "model_version": "wait_time_model_v_test"
        }
    ]

    # 2. Set up initial database state
    now = datetime.now(UTC)
    original_start_time = now + timedelta(hours=1)

    doctor = Doctor(name="Dr. Test", specialty="cardiology")
    patient = Patient(name="Test Patient")
    
    db_session.add(doctor)
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(doctor)
    db_session.refresh(patient)

    appointment = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        scheduled_at=original_start_time,
        status=AppointmentStatus.CONFIRMED
    )
    db_session.add(appointment)
    db_session.commit()
    db_session.refresh(appointment)

    # 3. Run the scheduling agent
    result = await run_proactive_scheduling(db_session)

    # 4. Assert the results
    assert result["overloads_detected"] == 1
    assert result["appointments_reassigned"] == 1

    # Verify the appointment was moved
    db_session.refresh(appointment)
    assert appointment.scheduled_at != original_start_time
    # The mock logic moves it by 2 hours
    expected_new_time = original_start_time + timedelta(hours=2)
    assert appointment.scheduled_at.replace(microsecond=0, tzinfo=None) == expected_new_time.replace(microsecond=0, tzinfo=None)
    # Verify notification was created
    notifications = db_session.query(Notification).all()
    assert len(notifications) == 1
    assert notifications[0].patient_id == patient.id
    assert "has been moved" in notifications[0].message
    assert "to ensure a shorter wait time" in notifications[0].message

    # Verify ops alert was created
    alerts = db_session.query(OpsAlert).all()
    assert len(alerts) == 1
    assert alerts[0].severity == 'warning'
    assert "Auto-reschedule due to overload" in alerts[0].message
    assert alerts[0].details["original_predicted_wait"] == 50.0
    assert alerts[0].details["appointment_id"] == appointment.id
