"""
Voice Service (v5.0)
====================

Central orchestrator for the complete audio pipeline:

    [audio bytes] → STT → BookingAgent → TTS → [audio file]

This module is called by:
- ``api/routes/voice.py`` — HTTP voice note uploads
- ``api/routes/webrtc.py`` — WebSocket streaming (agent + TTS step only)
"""

from __future__ import annotations

import logging
import os
import shutil

from services import stt_service, tts_service
from agents.orchestrator import orchestrator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fallback responses — returned when all STT providers fail
# ---------------------------------------------------------------------------

FALLBACK_RESPONSES = {
    "en": "I'm sorry, I couldn't understand that. Could you please try again?",
    "ur": "معذرت، میں سمجھ نہیں سکا۔ براہ کرم دوبارہ کوشش کریں۔",
}

# ---------------------------------------------------------------------------
# Static audio directory
# ---------------------------------------------------------------------------

STATIC_AUDIO_DIR = os.environ.get("STATIC_AUDIO_DIR", "static/audio")


def _ensure_static_dir() -> None:
    """Ensure the static audio directory exists."""
    os.makedirs(STATIC_AUDIO_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def handle_voice_request(audio_bytes: bytes, session_id: str) -> dict:
    """
    Entry point for HTTP voice note uploads (``/api/voice/chat``).

    Runs the full STT → Agent → TTS pipeline and returns a structured dict
    matching the v4 API contract so the frontend does not break.

    Args:
        audio_bytes: Raw audio content from the uploaded file.
        session_id: Unique session identifier.

    Returns:
        Dict with keys: ``transcript``, ``text_response``, ``audio_url``,
        ``detected_lang``, ``appointment``.
    """
    _ensure_static_dir()
    out_filename = f"out_{session_id}.mp3"
    out_path = os.path.join(STATIC_AUDIO_DIR, out_filename)

    # --- STT ---
    stt_result = await stt_service.transcribe_file(audio_bytes)
    transcript = stt_result["transcript"]
    lang = stt_result["lang"]

    # --- Empty transcript → canned response ---
    if not transcript.strip():
        canned = FALLBACK_RESPONSES.get(lang, FALLBACK_RESPONSES["en"])
        await tts_service.synthesize(canned, lang, out_path)
        return {
            "transcript": "",
            "text_response": canned,
            "audio_url": f"/static/audio/{out_filename}",
            "detected_lang": lang,
            "appointment": None,
        }

    # --- Agent ---
    response = await orchestrator.handle_booking(
        transcript, session_id, lang, mode="voice"
    )

    # --- TTS ---
    await tts_service.synthesize(response.message, lang, out_path)

    return {
        "transcript": transcript,
        "text_response": response.message,
        "audio_url": f"/static/audio/{out_filename}",
        "detected_lang": lang,
        "appointment": response.appointment_data,
    }
