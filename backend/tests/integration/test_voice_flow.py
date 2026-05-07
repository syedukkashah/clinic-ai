import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.voice_service import handle_voice_request

@pytest.mark.asyncio
async def test_voice_to_orchestrator_integration():
    """
    Test the voice pipeline end-to-end (STT -> Orchestrator -> Booking Agent -> TTS)
    without mocking the orchestrator or booking agent.
    We only mock the external API boundaries (STT, TTS, and LLM Router).
    """
    mock_stt = {"transcript": "I need a doctor", "lang": "en"}
    
    mock_llm_response = MagicMock()
    mock_llm_response.text = "I can help you book an appointment for general medicine."
    
    # Mock STT to return fake transcript
    with patch("services.voice_service.stt_service.transcribe_file", AsyncMock(return_value=mock_stt)):
        # Mock TTS to avoid making external calls
        with patch("services.voice_service.tts_service.synthesize", AsyncMock(return_value="/tmp/out.mp3")):
            # Mock the LLM router so the booking agent can execute without real keys
            with patch("agents.booking_agent.llm_router.call", AsyncMock(return_value=mock_llm_response)):
                result = await handle_voice_request(b"fake_audio", "test_integration_session")

    assert "transcript" in result
    assert "text_response" in result
    assert "audio_url" in result
    
    assert result["transcript"] == "I need a doctor"
    assert result["text_response"] == "I can help you book an appointment for general medicine."
    assert result["detected_lang"] == "en"
