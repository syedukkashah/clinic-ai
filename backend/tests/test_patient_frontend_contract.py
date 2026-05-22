from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from db.models import Doctor


class FakeRedis:
    def __init__(self):
        self.store = {}

    async def get(self, key):
        return self.store.get(key)

    async def setex(self, key, ttl, value):
        self.store[key] = value
        return True

    async def delete(self, key):
        self.store.pop(key, None)
        return True

    async def exists(self, key):
        return key in self.store


def _seed_doctor(db_session, doctor_id=1, name="Ahmed Raza", specialty="General Practice"):
    doctor = db_session.get(Doctor, doctor_id)
    if doctor is None:
        doctor = Doctor(
            id=doctor_id,
            name=name,
            specialty=specialty,
            is_available=True,
            avg_consult_duration=10,
        )
        db_session.add(doctor)
    else:
        doctor.name = name
        doctor.specialty = specialty
        doctor.is_available = True
    db_session.commit()
    return doctor


def test_patient_chat_contract_primary_endpoint(client):
    appointment = {
        "id": "apt-frontend",
        "patientName": "Rayyan",
        "patientId": "sess-frontend",
        "doctorName": "Dr. Ahmed Raza",
        "date": "2026-06-06",
        "time": "16:00",
    }
    trace = [
        {
            "type": "ACT",
            "tool": "get_available_slots",
            "provider": "groq",
            "args": {"specialty": "general"},
            "result": "Tool call selected by LLM",
            "latencyMs": 420,
        },
        {
            "type": "OBSERVE",
            "tool": "predict_wait_time",
            "provider": "gemini",
            "args": {"doctor_id": 1},
            "result": "Predicted wait time: 38 minutes.",
            "latencyMs": 980,
        },
    ]
    slots = [
        {
            "id": "slot-1-16:00",
            "doctorId": 1,
            "doctorName": "Dr. Ahmed Raza",
            "specialty": "General Practice",
            "date": "2026-06-06",
            "time": "16:00",
            "wait": 38,
            "predictedWaitMin": 38,
        }
    ]

    with patch("api.routes.chat.orchestrator.handle_booking", AsyncMock()) as mock_handle:
        mock_handle.return_value = SimpleNamespace(
            message="Appointment confirmed.",
            intent="booking_intent",
            appointment_data=appointment,
            tool_calls=trace,
            suggested_slots=slots,
        )
        res = client.post(
            "/api/chat",
            json={"userId": "sess-frontend", "message": "Book Dr Ahmed", "lang": "en"},
        )

    assert res.status_code == 200
    mock_handle.assert_awaited_once_with(
        transcript="Book Dr Ahmed",
        session_id="sess-frontend",
        lang="en",
        mode="text",
        redis=None,
    )
    body = res.json()
    assert body["responseText"] == "Appointment confirmed."
    assert body["detected_lang"] == "en"
    assert body["appointment"] == appointment
    assert body["suggestedSlots"][0]["wait"] == 38
    assert body["tool_calls"][0]["provider"] == "groq"
    assert body["tool_calls"][1]["provider"] == "gemini"


def test_patient_chat_contract_supports_legacy_agent_response(client):
    with patch("api.routes.chat.orchestrator.handle_booking", AsyncMock()) as mock_handle:
        mock_handle.return_value = SimpleNamespace(
            message="Clinic hours are Monday to Friday.",
            intent="informational_query",
        )
        res = client.post(
            "/api/chat",
            json={"userId": "sess-legacy", "message": "clinic hours", "lang": "en"},
        )

    assert res.status_code == 200
    body = res.json()
    assert body["response"] == "Clinic hours are Monday to Friday."
    assert body["appointment"] is None
    assert body["tool_calls"] == []
    assert body["suggestedSlots"] == []


def test_voice_chat_contract_exposes_transcript_language_trace_and_slots(client, tmp_path):
    response = SimpleNamespace(
        message="I found a slot with a short wait.",
        appointment_data=None,
        tool_calls=[
            {
                "type": "ACT",
                "tool": "get_available_slots",
                "provider": "gemini",
                "args": {"specialty": "general"},
                "result": "Tool call selected by LLM",
                "latencyMs": 510,
            }
        ],
        suggested_slots=[
            {
                "id": "slot-voice",
                "doctorId": 1,
                "doctorName": "Dr. Ahmed Raza",
                "specialty": "General Practice",
                "date": "2026-06-06",
                "time": "09:00",
                "wait": 12,
            }
        ],
    )

    with patch("services.voice_service.STATIC_AUDIO_DIR", str(tmp_path)), \
         patch("services.stt_service.transcribe_file", AsyncMock(return_value={"transcript": "I need a doctor", "lang": "en"})), \
         patch("services.tts_service.synthesize", AsyncMock(return_value=str(tmp_path / "out.mp3"))), \
         patch("services.voice_service.orchestrator.handle_booking", AsyncMock(return_value=response)) as mock_handle:
        res = client.post(
            "/api/voice/chat",
            files={"audio": ("voice.webm", BytesIO(b"audio"), "audio/webm")},
            data={"session_id": "voice-session"},
        )

    assert res.status_code == 200
    mock_handle.assert_awaited_once_with("I need a doctor", "voice-session", "en", mode="voice")
    body = res.json()
    assert body["transcript"] == "I need a doctor"
    assert body["text_response"] == "I found a slot with a short wait."
    assert body["detected_lang"] == "en"
    assert body["audio_url"].endswith("/out_voice-session.mp3")
    assert body["tool_calls"][0]["provider"] == "gemini"
    assert body["suggestedSlots"][0]["doctorName"] == "Dr. Ahmed Raza"


@pytest.mark.anyio
async def test_react_trace_preserves_provider_metadata_and_high_wait_slots():
    first = MagicMock()
    first.text = '{"tool": "get_available_slots", "args": {"specialty": "general"}}'
    first.provider = "groq"
    final = MagicMock()
    final.text = "Here are the best available slots."
    final.provider = "gemini"

    with patch("agents.booking_agent.llm_router") as mock_router, \
         patch.dict(
             "agents.booking_agent.TOOL_MAP",
             {"get_available_slots": AsyncMock(return_value="Dr. Ahmed Raza — slots: 09:00")},
         ), \
         patch(
             "agents.booking_agent._build_slot_suggestions",
             AsyncMock(
                 return_value=[
                     {
                         "id": "slot-high-wait",
                         "doctorId": 1,
                         "doctorName": "Dr. Ahmed Raza",
                         "specialty": "General Practice",
                         "date": "2026-06-06",
                         "time": "09:00",
                         "wait": 42,
                         "predictedWaitMin": 42,
                     }
                 ]
             ),
         ):
        mock_router.call = AsyncMock(side_effect=[first, final])
        from agents.booking_agent import process_chat_message

        result = await process_chat_message(
            user_id="trace-session",
            message="Show me general doctor availability",
            redis_client=None,
            language="en",
        )

    assert result["responseText"] == "Here are the best available slots."
    assert result["suggestedSlots"][0]["predictedWaitMin"] == 42
    providers = [step["provider"] for step in result["tool_calls"]]
    assert providers == ["groq", "groq", "gemini"]
    assert [step["type"] for step in result["tool_calls"]] == ["ACT", "OBSERVE", "CONCLUDE"]


def test_patient_chat_booking_persists_to_admin_appointments(client, db_session):
    _seed_doctor(db_session, doctor_id=1)
    session_id = "patient-e2e-session-v2"
    redis = FakeRedis()
    client.app.state.redis = redis

    try:
        with patch("agents.orchestrator.route_intent", AsyncMock(return_value="OPERATIONAL")):
            first = client.post(
                "/api/chat",
                json={
                    "userId": session_id,
                    "lang": "en",
                    "message": "Book an appointment",
                },
            )
            res = client.post(
                "/api/chat",
                json={
                    "userId": session_id,
                    "lang": "en",
                    "message": "Adeel Rehman, general, 2026-06-06, 4pm, fever, 03352034811",
                },
            )

        assert first.status_code == 200
        assert res.status_code == 200
        body = res.json()
        assert body["appointment"]["patientId"] == session_id
        assert body["appointment"]["doctorId"] == 1
        assert body["appointment"]["date"] == "2026-06-06"

        admin_res = client.get("/api/appointments/", params={"search": "Adeel"})
        assert admin_res.status_code == 200
        admin_body = admin_res.json()
        assert admin_body["total"] >= 1
        persisted = [item for item in admin_body["items"] if item["patientId"] == session_id]
        assert persisted
        assert persisted[0]["doctorName"] == "Ahmed Raza"
        assert persisted[0]["reason"] == "fever"
    finally:
        if hasattr(client.app.state, "redis"):
            client.app.state.redis = None


@pytest.mark.anyio
async def test_slot_suggestions_use_ml_wait_prediction_contract():
    from agents.booking_agent import _build_slot_suggestions

    doctor = {"id": 1, "name": "Ahmed Raza", "specialty": "General Practice"}
    with patch("agents.booking_agent.crud.get_doctors", AsyncMock(return_value=[doctor])), \
         patch(
             "agents.booking_agent.crud.get_doctor_availability",
             AsyncMock(return_value={"doctorId": 1, "availableSlots": ["08:00"]}),
         ), \
         patch(
             "agents.booking_agent.ml_service_client.get_wait_time",
             AsyncMock(return_value={"predicted_wait_minutes": 35}),
         ) as mock_wait:
        slots = await _build_slot_suggestions({"specialty": "general", "date": "2026-06-06"})

    mock_wait.assert_awaited_once()
    assert slots == [
        {
            "id": "slot-1-08:00",
            "doctorId": 1,
            "doctorName": "Dr. Ahmed Raza",
            "specialty": "General Practice",
            "date": "2026-06-06",
            "time": "08:00",
            "wait": 35,
            "predictedWaitMin": 35,
            "source": "db+ml_service",
        }
    ]
