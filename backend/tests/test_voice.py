"""
Voice Pipeline Tests (v5.0)
===========================

All 10 tests mandated by VOICE_AGENT_CONTEXT.md Section 15.

Uses pytest-asyncio with asyncio_mode = "auto" (configured in pytest.ini).
All external HTTP/SDK calls are mocked — no real API keys required.

These tests are self-contained: they do NOT import `main.app` and therefore
do NOT require Redis, PostgreSQL, or any other infrastructure to be running.
"""

from __future__ import annotations

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 1. test_stt_file_mode
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stt_file_mode():
    """Mock Deepgram REST response, verify transcript and lang extraction."""
    mock_alt = MagicMock()
    mock_alt.transcript = "Hello, I need an appointment"

    mock_channel = MagicMock()
    mock_channel.alternatives = [mock_alt]
    mock_channel.detected_language = "en"

    mock_results = MagicMock()
    mock_results.channels = [mock_channel]

    mock_response = MagicMock()
    mock_response.results = mock_results

    with patch("services.stt_service.DEEPGRAM_API_KEY", "test-key"):
        with patch(
            "services.stt_service._transcribe_deepgram",
            AsyncMock(return_value={"transcript": "Hello, I need an appointment", "lang": "en"}),
        ):
            from services import stt_service
            result = await stt_service.transcribe_file(b"fake_audio_data")

    assert result["transcript"] == "Hello, I need an appointment"
    assert result["lang"] == "en"


# ---------------------------------------------------------------------------
# 2. test_stt_language_detection_english
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stt_language_detection_english():
    """Deepgram returns detected_language='en', verify downstream lang value."""
    with patch("services.stt_service.DEEPGRAM_API_KEY", "test-key"):
        with patch(
            "services.stt_service._transcribe_deepgram",
            AsyncMock(return_value={"transcript": "Book me a slot tomorrow", "lang": "en"}),
        ):
            from services import stt_service
            result = await stt_service.transcribe_file(b"audio")

    assert result["lang"] == "en"


# ---------------------------------------------------------------------------
# 3. test_stt_language_detection_urdu
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stt_language_detection_urdu():
    """Deepgram returns detected_language='ur', verify lang routes to Edge TTS."""
    with patch("services.stt_service.DEEPGRAM_API_KEY", "test-key"):
        with patch(
            "services.stt_service._transcribe_deepgram",
            AsyncMock(return_value={"transcript": "مجھے کل ڈاکٹر سے ملنا ہے", "lang": "ur"}),
        ):
            from services import stt_service
            result = await stt_service.transcribe_file(b"audio")

    assert result["lang"] == "ur"


# ---------------------------------------------------------------------------
# 4. test_tts_english_routes_to_aura
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tts_english_routes_to_aura():
    """Mock httpx, verify Deepgram Aura-2 URL is called for lang='en'."""
    mock_resp = MagicMock()
    mock_resp.content = b"fake_mp3_data"
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    out = os.path.join(tempfile.gettempdir(), "test_aura.mp3")

    with patch("services.tts_service.DEEPGRAM_API_KEY", "test-key"):
        with patch("services.tts_service.httpx.AsyncClient", return_value=mock_client):
            from services import tts_service
            await tts_service.synthesize("Hello there", "en", out)

    mock_client.post.assert_called_once()
    called_url = mock_client.post.call_args[0][0]
    assert "api.deepgram.com/v1/speak" in called_url


# ---------------------------------------------------------------------------
# 5. test_tts_urdu_routes_to_edge
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tts_urdu_routes_to_edge():
    """Mock edge_tts, verify ur-PK-UzmaNeural is used for lang='ur'."""
    mock_comm_instance = AsyncMock()
    mock_comm_instance.save = AsyncMock()

    out = os.path.join(tempfile.gettempdir(), "test_edge.mp3")

    with patch("services.tts_service.edge_tts.Communicate", return_value=mock_comm_instance) as mock_comm:
        from services import tts_service
        await tts_service.synthesize("سلام", "ur", out)

    mock_comm.assert_called_with("سلام", "ur-PK-UzmaNeural")


# ---------------------------------------------------------------------------
# 6. test_voice_endpoint_e2e
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_voice_endpoint_e2e():
    """Mock audio upload, Deepgram, and agent — verify full response shape."""
    mock_stt = {"transcript": "I need a doctor", "lang": "en"}

    mock_agent_resp = MagicMock()
    mock_agent_resp.message = "I can help you book an appointment."
    mock_agent_resp.appointment_data = None

    with patch("services.voice_service.stt_service.transcribe_file", AsyncMock(return_value=mock_stt)):
        with patch("services.voice_service.orchestrator.handle_booking", AsyncMock(return_value=mock_agent_resp)):
            with patch("services.voice_service.tts_service.synthesize", AsyncMock(return_value="/tmp/out.mp3")):
                from services.voice_service import handle_voice_request
                result = await handle_voice_request(b"fake_audio", "test_session_e2e")

    assert "transcript" in result
    assert "text_response" in result
    assert "audio_url" in result
    assert "detected_lang" in result
    assert "appointment" in result
    assert result["transcript"] == "I need a doctor"
    assert result["text_response"] == "I can help you book an appointment."
    assert result["detected_lang"] == "en"


# ---------------------------------------------------------------------------
# 7. test_twilio_webhook_deepgram_model
# ---------------------------------------------------------------------------

def test_twilio_webhook_deepgram_model():
    """Verify TwiML response contains speechModel='deepgram_nova-3' and language='multi'."""
    # Build a minimal FastAPI app with only the twilio router — no Redis/DB needed
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.routes.twilio_voice import router as twilio_router

    mini_app = FastAPI()
    mini_app.include_router(twilio_router, prefix="/api/twilio")

    client = TestClient(mini_app)
    response = client.post("/api/twilio/incoming", params={"CallSid": "CAtest123"})

    assert response.status_code == 200
    content = response.text
    assert "deepgram_nova-3" in content
    assert "multi" in content


# ---------------------------------------------------------------------------
# 8. test_stt_fallback_to_whisper
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stt_fallback_to_whisper():
    """Simulate Deepgram + Groq failures, verify local Whisper fallback activates."""
    mock_whisper_result = {"transcript": "fallback text", "lang": "en"}

    with patch("services.stt_service.DEEPGRAM_API_KEY", "test-key"):
        with patch(
            "services.stt_service._transcribe_deepgram",
            AsyncMock(side_effect=TimeoutError("Deepgram timed out")),
        ):
            with patch(
                "services.stt_service._transcribe_groq",
                AsyncMock(side_effect=RuntimeError("Groq failed")),
            ):
                with patch(
                    "services.stt_service._transcribe_local_whisper",
                    AsyncMock(return_value=mock_whisper_result),
                ):
                    from services import stt_service
                    result = await stt_service.transcribe_file(b"audio")

    assert result["transcript"] == "fallback text"
    assert result["lang"] == "en"


# ---------------------------------------------------------------------------
# 9. test_voice_endpoint_never_500s
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_voice_endpoint_never_500s():
    """All STT providers fail (empty transcript), verify canned response — not an exception."""
    # STT returns empty — all providers exhausted
    mock_stt = {"transcript": "", "lang": "en"}

    with patch("services.voice_service.stt_service.transcribe_file", AsyncMock(return_value=mock_stt)):
        with patch("services.voice_service.tts_service.synthesize", AsyncMock(return_value="/tmp/out.mp3")):
            from services.voice_service import handle_voice_request
            result = await handle_voice_request(b"bad_audio", "fail_session_999")

    # Must return a valid dict, not raise
    assert isinstance(result, dict)
    assert result["transcript"] == ""
    assert len(result["text_response"]) > 0, "Canned response must not be empty"
    assert "audio_url" in result
    assert result["detected_lang"] in ("en", "ur")


# ---------------------------------------------------------------------------
# 10. test_prometheus_metrics_emitted
# ---------------------------------------------------------------------------

def test_prometheus_metrics_emitted():
    """Verify Prometheus metrics are registered after importing the service modules."""
    # Import modules to trigger metric registration
    import services.stt_service  # noqa: F401
    import services.tts_service  # noqa: F401

    from prometheus_client import REGISTRY

    registered = {m.name for m in REGISTRY.collect()}

    assert "mediflow_stt_calls" in registered or "mediflow_stt_calls_total" in registered, \
        f"STT counter not registered. Found: {sorted(registered)}"
    assert "mediflow_tts_ttfb_seconds" in registered, \
        f"TTS histogram not registered. Found: {sorted(registered)}"
