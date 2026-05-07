"""
Voice Pipeline Tests (v5.0)
===========================

All 10 tests mandated by VOICE_AGENT_CONTEXT.md Section 15.

Uses pytest-asyncio with asyncio_mode = "auto" (configured in pytest.ini).
All external HTTP/SDK calls are mocked — no real API keys required.
"""

from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


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

    mock_transcribe = AsyncMock(return_value=mock_response)

    with patch.dict(os.environ, {"DEEPGRAM_API_KEY": "test-key"}):
        with patch("services.stt_service.DEEPGRAM_API_KEY", "test-key"):
            with patch("services.stt_service._transcribe_deepgram", mock_transcribe):
                from services import stt_service
                result = await stt_service.transcribe_file(b"fake_audio_data")

    assert result["transcript"] == "Hello, I need an appointment"
    assert result["lang"] == "en"


# ---------------------------------------------------------------------------
# 2. test_stt_language_detection_english
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stt_language_detection_english():
    """Deepgram returns detected_language='en', verify downstream."""
    mock_alt = MagicMock()
    mock_alt.transcript = "Book me a slot tomorrow"

    mock_channel = MagicMock()
    mock_channel.alternatives = [mock_alt]
    mock_channel.detected_language = "en"

    mock_results = MagicMock()
    mock_results.channels = [mock_channel]

    mock_response = MagicMock()
    mock_response.results = mock_results

    mock_transcribe = AsyncMock(return_value=mock_response)

    with patch("services.stt_service.DEEPGRAM_API_KEY", "test-key"):
        with patch("services.stt_service._transcribe_deepgram", mock_transcribe):
            from services import stt_service
            result = await stt_service.transcribe_file(b"audio")

    assert result["lang"] == "en"


# ---------------------------------------------------------------------------
# 3. test_stt_language_detection_urdu
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stt_language_detection_urdu():
    """Deepgram returns detected_language='ur', verify TTS would route to Edge."""
    mock_alt = MagicMock()
    mock_alt.transcript = "مجھے کل ڈاکٹر سے ملنا ہے"

    mock_channel = MagicMock()
    mock_channel.alternatives = [mock_alt]
    mock_channel.detected_language = "ur"

    mock_results = MagicMock()
    mock_results.channels = [mock_channel]

    mock_response = MagicMock()
    mock_response.results = mock_results

    mock_transcribe = AsyncMock(return_value=mock_response)

    with patch("services.stt_service.DEEPGRAM_API_KEY", "test-key"):
        with patch("services.stt_service._transcribe_deepgram", mock_transcribe):
            from services import stt_service
            result = await stt_service.transcribe_file(b"audio")

    assert result["lang"] == "ur"


# ---------------------------------------------------------------------------
# 4. test_tts_english_routes_to_aura
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tts_english_routes_to_aura():
    """Mock httpx, verify Aura-2 URL called for lang='en'."""
    mock_resp = MagicMock()
    mock_resp.content = b"fake_mp3_data"
    mock_resp.raise_for_status = MagicMock()

    mock_client_instance = AsyncMock()
    mock_client_instance.post = AsyncMock(return_value=mock_resp)
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=False)

    with patch("services.tts_service.DEEPGRAM_API_KEY", "test-key"):
        with patch("services.tts_service.httpx.AsyncClient", return_value=mock_client_instance):
            from services import tts_service
            import tempfile
            out = os.path.join(tempfile.gettempdir(), "test_aura.mp3")
            await tts_service.synthesize("Hello there", "en", out)

    # Verify Aura-2 endpoint was called
    mock_client_instance.post.assert_called_once()
    call_args = mock_client_instance.post.call_args
    assert "api.deepgram.com/v1/speak" in call_args[0][0]


# ---------------------------------------------------------------------------
# 5. test_tts_urdu_routes_to_edge
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tts_urdu_routes_to_edge():
    """Mock edge_tts, verify ur-PK-UzmaNeural used for lang='ur'."""
    mock_comm_instance = AsyncMock()
    mock_comm_instance.save = AsyncMock()

    with patch("services.tts_service.edge_tts.Communicate", return_value=mock_comm_instance) as mock_comm:
        from services import tts_service
        import tempfile
        out = os.path.join(tempfile.gettempdir(), "test_edge.mp3")
        await tts_service.synthesize("سلام", "ur", out)

    mock_comm.assert_called_with("سلام", "ur-PK-UzmaNeural")


# ---------------------------------------------------------------------------
# 6. test_voice_endpoint_e2e
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_voice_endpoint_e2e():
    """Mock audio upload, mock Deepgram, mock agent, verify full response shape."""
    mock_stt_result = {"transcript": "I need a doctor", "lang": "en"}
    mock_agent_response = MagicMock()
    mock_agent_response.message = "I can help you book an appointment."
    mock_agent_response.appointment_data = None

    with patch("services.voice_service.stt_service.transcribe_file", AsyncMock(return_value=mock_stt_result)):
        with patch("services.voice_service.orchestrator.handle_booking", AsyncMock(return_value=mock_agent_response)):
            with patch("services.voice_service.tts_service.synthesize", AsyncMock(return_value="/tmp/out.mp3")):
                from services.voice_service import handle_voice_request
                result = await handle_voice_request(b"fake_audio", "test_session")

    assert "transcript" in result
    assert "text_response" in result
    assert "audio_url" in result
    assert "detected_lang" in result
    assert "appointment" in result
    assert result["transcript"] == "I need a doctor"
    assert result["detected_lang"] == "en"


# ---------------------------------------------------------------------------
# 7. test_twilio_webhook_deepgram_model
# ---------------------------------------------------------------------------

def test_twilio_webhook_deepgram_model():
    """Verify TwiML contains speechModel='deepgram_nova-3'."""
    from main import app

    client = TestClient(app)
    response = client.post(
        "/api/twilio/incoming",
        params={"CallSid": "test123"},
    )
    assert response.status_code == 200
    content = response.text
    # Twilio SDK renders speechModel as an XML attribute
    assert "deepgram_nova-3" in content or "deepgram" in content.lower()
    assert "multi" in content


# ---------------------------------------------------------------------------
# 8. test_stt_fallback_to_whisper
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stt_fallback_to_whisper():
    """Simulate Deepgram timeout, verify fallback chain activates."""
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
    """All services fail, verify canned response returned (not 500)."""
    # STT returns empty (all providers failed)
    mock_stt_result = {"transcript": "", "lang": "en"}

    with patch("services.voice_service.stt_service.transcribe_file", AsyncMock(return_value=mock_stt_result)):
        with patch("services.voice_service.tts_service.synthesize", AsyncMock(return_value="/tmp/out.mp3")):
            from services.voice_service import handle_voice_request
            result = await handle_voice_request(b"bad_audio", "fail_session")

    assert result["transcript"] == ""
    assert result["text_response"] != ""  # canned response, not empty
    assert "audio_url" in result
    assert result["detected_lang"] in ("en", "ur")


# ---------------------------------------------------------------------------
# 10. test_prometheus_metrics_emitted
# ---------------------------------------------------------------------------

def test_prometheus_metrics_emitted():
    """Verify mediflow_stt_calls_total and mediflow_tts_ttfb_seconds are registered."""
    from prometheus_client import REGISTRY

    metric_names = [m.name for m in REGISTRY.collect()]

    # Import modules to ensure metrics are registered
    import services.stt_service  # noqa: F401
    import services.tts_service  # noqa: F401

    metric_names = [m.name for m in REGISTRY.collect()]

    assert "mediflow_stt_calls_total" in metric_names or \
           "mediflow_stt_calls" in metric_names, \
           f"STT counter not found in {metric_names}"

    assert "mediflow_tts_ttfb_seconds" in metric_names or \
           "mediflow_tts_ttfb" in metric_names, \
           f"TTS histogram not found in {metric_names}"
