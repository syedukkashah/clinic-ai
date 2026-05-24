from datetime import date, datetime, timezone

from db.models import (
    AgentRun,
    AnomalyPrediction,
    Appointment,
    AppointmentStatus,
    BookingChannel,
    Doctor,
    MLPrediction,
    Notification,
    OpsAlert,
    Patient,
    Slot,
)


def test_admin_read_api_surfaces_existing_tables(client, db_session):
    patient = Patient(id="admin-patient-1", name="Admin Test Patient", preferred_lang="en")
    doctor = Doctor(id=9101, name="Dr. Admin Test", specialty="General")
    appointment = Appointment(
        id="admin-apt-1",
        patient_id=patient.id,
        doctor_id=doctor.id,
        slot_id=99101,
        scheduled_at=datetime(2026, 5, 23, 10, 0, tzinfo=timezone.utc),
        date=date(2026, 5, 23),
        time="10:00",
        status=AppointmentStatus.CONFIRMED,
        predicted_wait_min=14,
        actual_wait_minutes=16,
        booking_channel=BookingChannel.VOICE_NOTE,
        reason="Follow-up",
    )
    slot = Slot(
        id=99101,
        doctor_id=doctor.id,
        start_time=datetime(2026, 5, 23, 10, 0, tzinfo=timezone.utc),
        is_available=False,
    )
    prediction = MLPrediction(
        model_name="wait_time_model",
        model_version="v_test",
        appointment_id=appointment.id,
        target_doctor_id=doctor.id,
        target_date=date(2026, 5, 23),
        target_hour=10,
        input_features={"doctor_id": doctor.id, "queue_depth": 2},
        predicted_value=14,
        actual_value=16,
        resolved_at=datetime(2026, 5, 23, 11, 0, tzinfo=timezone.utc),
    )
    notification = Notification(
        patient_id=patient.id,
        appointment_id=appointment.id,
        message="Appointment confirmed for Admin Test Patient",
        notification_type="patient",
        is_mock=True,
    )
    alert = OpsAlert(
        message="Admin alert test",
        severity="WARNING",
        channel="admin",
        agent="ops_monitor",
        details={"reasoning": "Checked admin route", "type": "test", "acknowledged": False},
    )
    reassignment_alert = OpsAlert(
        message="Auto-reschedule due to overload for Dr. Admin Test.",
        severity="warning",
        channel="admin",
        agent="scheduling_agent",
        details={
            "appointment_id": appointment.id,
            "original_doctor_id": doctor.id,
            "new_doctor_id": doctor.id,
            "original_predicted_wait": 48,
            "new_predicted_wait": 18,
            "original_start_time": "2026-05-23T10:00:00+00:00",
            "new_start_time": "2026-05-23T12:00:00+00:00",
            "trigger": "proactive_scheduling_agent",
        },
    )
    agent_run = AgentRun(
        agent="booking_agent",
        session_id="admin-session-1",
        mode="text",
        language="en",
        outcome="booked",
        providers_used=["groq", "gemini"],
        tool_calls=[
            {
                "type": "ACT",
                "tool": "get_available_slots",
                "provider": "groq",
                "args": {"specialty": "General"},
                "result": "Tool call selected by LLM",
                "latencyMs": 120,
            },
            {
                "type": "CONCLUDE",
                "tool": "booking_agent",
                "provider": "gemini",
                "args": {"lang": "en"},
                "result": "Appointment booked",
                "latencyMs": 180,
            },
        ],
        steps_count=2,
        duration_ms=300,
        summary="Appointment booked",
    )
    anomaly = AnomalyPrediction(type="booking_volume", value=-0.42, metadata_json={"window": "5m"})

    db_session.add_all([patient, doctor, slot, appointment, prediction, notification, alert, reassignment_alert, agent_run, anomaly])
    db_session.commit()

    notifications = client.get("/api/admin/notifications?limit=5")
    assert notifications.status_code == 200
    assert any(item["appointment_id"] == "admin-apt-1" for item in notifications.json())

    predictions = client.get("/api/admin/ml/predictions?model=wait_time_model&limit=5")
    assert predictions.status_code == 200
    assert any(item["appointment_id"] == "admin-apt-1" for item in predictions.json())

    model_status = client.get("/api/admin/ml/model-status?name=wait_time_model")
    assert model_status.status_code == 200
    body = model_status.json()
    assert body["name"] == "wait_time_model"
    assert body["resolved_count"] >= 1
    assert body["metric_name"] == "RMSE"

    voice_sessions = client.get("/api/admin/voice-sessions?limit=5")
    assert voice_sessions.status_code == 200
    assert any(item["session_id"] == "admin-apt-1" for item in voice_sessions.json())

    slots = client.get("/api/slots?doctor_id=9101&date=2026-05-23")
    assert slots.status_code == 200
    slot_rows = slots.json()["items"]
    assert any(item["appointment_id"] == "admin-apt-1" for item in slot_rows)

    reassignments = client.get("/api/admin/reassignments?limit=5")
    assert reassignments.status_code == 200
    assert any(item["appointment_id"] == "admin-apt-1" and item["predicted_wait_after"] == 18 for item in reassignments.json())

    anomaly_history = client.get("/api/admin/anomaly-history?limit=5")
    assert anomaly_history.status_code == 200
    assert any(item["is_anomaly"] for item in anomaly_history.json())

    summary = client.get("/api/admin/stats/summary")
    assert summary.status_code == 200
    assert "total_bookings_today" in summary.json()

    agent_runs = client.get("/api/admin/agent-runs?agent=booking&limit=5")
    assert agent_runs.status_code == 200
    runs = agent_runs.json()
    assert any(item["session_id"] == "admin-session-1" for item in runs)
    run = next(item for item in runs if item["session_id"] == "admin-session-1")
    assert run["providers_used"] == ["groq", "gemini"]
    assert run["tool_calls"][0]["tool"] == "get_available_slots"

    key_events = client.get("/api/admin/llm/key-events")
    assert key_events.status_code == 200
    assert isinstance(key_events.json(), list)
