"""
Twilio Voice Webhooks (v5.0)
============================

Handles incoming Twilio phone calls with Deepgram Nova-3 as the speech model.

Endpoints:
    POST /api/twilio/incoming  — initial greeting + Gather
    POST /api/twilio/process   — process speech result, run agent + TTS

Changes from v4:
    - ``speechModel="deepgram_nova-3"`` replaces ``language="ur-PK"``
    - ``language="multi"`` enables code-switching (Urdish)
    - Language detection uses Arabic-character heuristic (Twilio doesn't
      pass ``detected_language`` from Deepgram back to the webhook)
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Form, Request, Response

from agents.orchestrator import orchestrator
from services import tts_service

logger = logging.getLogger(__name__)

router = APIRouter()

STATIC_AUDIO_DIR = os.environ.get("STATIC_AUDIO_DIR", "static/audio")
APP_DOMAIN = os.environ.get("APP_DOMAIN", "https://localhost:8000")


# ---------------------------------------------------------------------------
# Language detection heuristic (Twilio path only)
# ---------------------------------------------------------------------------

def _detect_lang_from_transcript(text: str) -> str:
    """
    Heuristic for the Twilio path — Deepgram already transcribed,
    we just need the language for TTS routing.
    """
    urdu_chars = set("ابپتٹثجچحخدڈذرڑزژسشصضطظعغفقکگلمنوہھیے")
    urdu_count = sum(1 for ch in text if ch in urdu_chars)
    return "ur" if urdu_count > len(text) * 0.3 else "en"


# ---------------------------------------------------------------------------
# Incoming call — initial greeting
# ---------------------------------------------------------------------------

@router.post("/incoming")
async def incoming_call(request: Request):
    """
    Handle an incoming Twilio phone call.

    Returns TwiML that greets the caller and starts a Gather
    with Deepgram Nova-3 as the speech model.
    """
    from twilio.twiml.voice_response import VoiceResponse, Gather

    session_id = f"twilio_{request.query_params.get('CallSid', 'unknown')}"
    resp = VoiceResponse()
    gather = Gather(
        input="speech",
        action=f"/api/twilio/process?session_id={session_id}",
        timeout=5,
        speech_timeout="auto",
        speech_model="deepgram_nova-3",
        language="multi",
    )
    gather.say(
        "میڈی فلو میں خوش آمدید۔ میں آپ کی کیسے مدد کر سکتا ہوں؟",
        language="ur-PK",
    )
    resp.append(gather)
    resp.redirect("/api/twilio/incoming")
    return Response(content=str(resp), media_type="text/xml")


# ---------------------------------------------------------------------------
# Process speech result
# ---------------------------------------------------------------------------

@router.post("/process")
async def process_speech(
    request: Request,
    SpeechResult: str = Form(""),
    session_id: str = "",
    CallSid: str = Form(""),
):
    """
    Process speech recognized by Twilio (via Deepgram Nova-3).

    Twilio passes the transcript as ``SpeechResult``. We detect the
    language, run the agent, synthesize TTS, and return TwiML that
    plays the audio and re-gathers.
    """
    from twilio.twiml.voice_response import VoiceResponse, Gather

    # Get session_id from query params if not in form
    if not session_id:
        session_id = request.query_params.get("session_id", f"twilio_{CallSid}")

    transcript = SpeechResult
    lang = _detect_lang_from_transcript(transcript)

    logger.info(
        "Twilio speech — session=%s lang=%s transcript=%s",
        session_id,
        lang,
        transcript[:80],
    )

    # Agent
    response = await orchestrator.handle_booking(
        transcript, session_id, lang, mode="voice"
    )

    # TTS
    os.makedirs(STATIC_AUDIO_DIR, exist_ok=True)
    audio_filename = f"twilio_{CallSid or session_id}.mp3"
    audio_path = os.path.join(STATIC_AUDIO_DIR, audio_filename)
    await tts_service.synthesize(response.message, lang, audio_path)

    # Build TwiML response
    twiml = VoiceResponse()
    twiml.play(f"{APP_DOMAIN}/static/audio/{audio_filename}")
    gather = Gather(
        input="speech",
        action=f"/api/twilio/process?session_id={session_id}",
        timeout=5,
        speech_timeout="auto",
        speech_model="deepgram_nova-3",
        language="multi",
    )
    twiml.append(gather)
    twiml.hangup()
    return Response(content=str(twiml), media_type="text/xml")
