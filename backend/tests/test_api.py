import re
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock


def _materialize_path(path_template: str) -> str:
    def repl(match: re.Match[str]) -> str:
        name = match.group(0).strip("{}").lower()
        if "uuid" in name:
            return "00000000-0000-0000-0000-000000000000"
        if "id" in name or name.endswith("pk"):
            return "test-id"
        return "test"

    return re.sub(r"\{[^}]+\}", repl, path_template)


def test_openapi_schema_loads(client):
    res = client.get("/openapi.json")
    assert res.status_code == 200
    schema = res.json()
    assert "paths" in schema


def test_all_openapi_endpoints_do_not_500_on_minimal_requests(client):
    schema = client.get("/openapi.json").json()
    paths = schema.get("paths", {})
    assert paths

    failures: list[str] = []
    for path, methods in paths.items():
        if path in {"/openapi.json", "/docs", "/redoc"}:
            continue

        materialized = _materialize_path(path)
        for method, _spec in methods.items():
            method_lc = method.lower()
            if method_lc not in {"get", "post", "put", "patch", "delete"}:
                continue

            request_fn = getattr(client, method_lc)
            try:
                with patch("services.tts_service.synthesize", AsyncMock(return_value="/tmp/test.mp3")):
                    with patch("services.stt_service.transcribe_file", AsyncMock(return_value={"transcript": "test", "lang": "en"})):
                        with patch("agents.booking_agent.llm_router.call", AsyncMock()) as mock_llm:
                            mock_resp = type('MockResponse', (), {})()
                            mock_resp.text = "Test response"
                            mock_llm.return_value = mock_resp
                            if method_lc in {"post", "put", "patch"}:
                                resp = request_fn(materialized, json={})
                            else:
                                resp = request_fn(materialized)
            except Exception as e:
                failures.append(f"{method_lc.upper()} {materialized} raised {type(e).__name__}: {e}")
                continue

            if resp.status_code >= 500 and resp.status_code != 501:
                failures.append(f"{method_lc.upper()} {materialized} returned {resp.status_code}: {resp.text[:500]}")

    assert not failures, "\n".join(failures)


def test_auth_login_demo_accounts(client):
    with patch("api.routes.auth.settings.ALLOW_DEMO_AUTH", True):
        res = client.post(
            "/api/auth/login/access-token",
            data={"username": "admin@mediflow.io", "password": "demo"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    assert res.status_code == 200
    body = res.json()
    assert "accessToken" in body
    assert body.get("tokenType") == "bearer"


def test_chat_message_endpoint(client):
    with patch("api.routes.chat.orchestrator.handle_booking", AsyncMock()) as mock_handle:
        mock_handle.return_value = SimpleNamespace(
            message="Hello! How can I help you today?",
            intent="general_query",
        )
        res = client.post("/api/chat/message", json={"userId": "u1", "message": "hello"})
    assert res.status_code == 200
    body = res.json()
    assert "response" in body
    assert body.get("agentId") == "orchestrator"


def test_chat_message_endpoint_uses_orchestrator(client):
    with patch("api.routes.chat.orchestrator.handle_booking", AsyncMock()) as mock_handle:
        mock_handle.return_value = SimpleNamespace(
            message="Clinic hours are Monday to Friday, 9:00 AM to 5:00 PM.",
            intent="general_query",
        )
        res = client.post(
            "/api/chat/message",
            json={"userId": "patient-session", "message": "what are clinic timings"},
        )
    assert res.status_code == 200
    mock_handle.assert_awaited_once_with(
        transcript="what are clinic timings",
        session_id="patient-session",
        lang="en",
        mode="text",
    )
    assert "Clinic hours" in res.json()["response"]


def test_chat_message_endpoint_passes_language(client):
    with patch("api.routes.chat.orchestrator.handle_booking", AsyncMock()) as mock_handle:
        mock_handle.return_value = SimpleNamespace(
            message="السلام علیکم! کلینک کے اوقات صبح 9 سے شام 5 تک ہیں۔",
            intent="general_query",
        )
        res = client.post(
            "/api/chat/message",
            json={"userId": "patient-session", "message": "کلینک اوقات", "lang": "ur"},
        )
    assert res.status_code == 200
    mock_handle.assert_awaited_once_with(
        transcript="کلینک اوقات",
        session_id="patient-session",
        lang="ur",
        mode="text",
    )
    body = res.json()
    assert body["response"] == body["responseText"]


from db.models import Patient, Doctor
from io import BytesIO


def test_voice_chat_endpoint(client):
    with patch("services.tts_service.synthesize", AsyncMock(return_value="/tmp/test.mp3")):
        with patch("services.stt_service.transcribe_file", AsyncMock(return_value={"transcript": "Hello, I need a doctor", "lang": "en"})):
            with patch("agents.booking_agent.llm_router.call", AsyncMock()) as mock_llm:
                mock_resp = type('MockResponse', (), {})()
                mock_resp.text = "I can help you book an appointment!"
                mock_llm.return_value = mock_resp
                audio_file = BytesIO(b"fake_audio_data")
                res = client.post("/api/voice/chat", files={"audio": ("test.mp3", audio_file, "audio/mpeg")}, data={"session_id": "test-session-123"})
    assert res.status_code == 200
    body = res.json()
    assert "transcript" in body
    assert "text_response" in body
    assert "audio_url" in body
    assert body["transcript"] == "Hello, I need a doctor"
    assert body["text_response"] == "I can help you book an appointment!"

def test_appointments_crud_happy_path(client, db_session):
    patient = Patient(id="pat-1", name="Test Patient")
    doctor = Doctor(id=1, name="Dr. Test", specialty="General")
    db_session.add(patient)
    db_session.add(doctor)
    db_session.commit()

    create_payload = {
        "patientName": "Test Patient",
        "patientId": "pat-1",
        "doctorId": 1,
        "doctorName": "Dr. Test",
        "time": "09:00",
        "date": "2026-01-01",
        "reason": "Consultation",
        "urgency": "moderate",
    }
    created = client.post("/api/appointments/", json=create_payload)
    assert created.status_code == 200
    created_body = created.json()
    assert "id" in created_body
    apt_id = created_body["id"]

    updated = client.put(f"/api/appointments/{apt_id}", json={"reason": "Follow-up"})
    assert updated.status_code == 200
    assert updated.json().get("reason") == "Follow-up"

    deleted = client.delete(f"/api/appointments/{apt_id}")
    assert deleted.status_code == 200
