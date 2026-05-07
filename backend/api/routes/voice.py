"""
Voice Route (v5.0)
==================

HTTP endpoint for voice note uploads. Replaces the v4 inline STT/TTS logic
with a single call to ``voice_service.handle_voice_request()``.

Endpoint:
    POST /api/voice/chat
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Form, UploadFile

from services.voice_service import handle_voice_request

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat")
async def voice_chat(audio: UploadFile, session_id: str = Form(...)):
    """
    Accept a voice note upload, transcribe, route through the agent,
    and return text + synthesized audio.

    The response shape is identical to v4 so the frontend does not break::

        {
            "transcript": "...",
            "text_response": "...",
            "audio_url": "/static/audio/out_{session_id}.mp3",
            "detected_lang": "en" | "ur",
            "appointment": null | { ... }
        }
    """
    audio_bytes = await audio.read()
    result = await handle_voice_request(audio_bytes, session_id)
    return result
