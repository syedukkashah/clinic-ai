"""
WebRTC Voice WebSocket (v5.0)
=============================

Streams 250ms audio chunks from the browser to Deepgram Nova-3 for
real-time transcription. Partial transcripts are forwarded to the client
for live display; final transcripts trigger the agent + TTS pipeline.

Endpoint:
    WS /ws/voice/{session_id}

Message protocol (server → client):
    - ``{"type": "partial", "text": "...", "lang": "en"}``  — live transcription
    - ``{"type": "final", "text": "...", "transcript": "...", "detected_lang": "en", "appointment": null}``
    - binary bytes — synthesized audio response (MP3)
    - ``{"type": "error", "text": "..."}``
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from agents.orchestrator import orchestrator
from services import stt_service, tts_service

logger = logging.getLogger(__name__)

router = APIRouter()

STATIC_AUDIO_DIR = os.environ.get("STATIC_AUDIO_DIR", "static/audio")


@router.websocket("/voice/{session_id}")
async def ws_voice(ws: WebSocket, session_id: str):
    """
    WebSocket handler for real-time voice streaming.

    Flow:
    1. Accept browser WebSocket
    2. Open persistent Deepgram live connection
    3. Pipe each 250ms chunk to Deepgram
    4. Forward partial transcripts to client
    5. On final transcript → run agent + TTS → send audio back
    """
    await ws.accept()
    logger.info("WebRTC WS connected — session=%s", session_id)

    dg_connection = None
    final_lang = "en"

    async def _on_transcript(sentence: str, lang: str, is_final: bool):
        """Callback from Deepgram streaming transcription."""
        nonlocal final_lang
        final_lang = lang

        if not is_final:
            # Partial transcript — forward for live display
            await ws.send_json({
                "type": "partial",
                "text": sentence,
                "lang": lang,
            })
        else:
            # Final transcript — run the full pipeline
            try:
                await ws.send_json({
                    "type": "partial",
                    "text": sentence,
                    "lang": lang,
                })

                # Agent
                response = await orchestrator.handle_booking(
                    sentence, session_id, lang, mode="voice"
                )

                # TTS
                os.makedirs(STATIC_AUDIO_DIR, exist_ok=True)
                out_path = os.path.join(
                    STATIC_AUDIO_DIR, f"ws_{session_id}.mp3"
                )
                await tts_service.synthesize(response.message, lang, out_path)

                # Send final text
                await ws.send_json({
                    "type": "final",
                    "text": response.message,
                    "transcript": sentence,
                    "detected_lang": lang,
                    "appointment": response.appointment_data,
                })

                # Send audio bytes
                with open(out_path, "rb") as f:
                    audio_data = f.read()
                await ws.send_bytes(audio_data)

            except Exception as e:
                logger.error("Pipeline error in WS voice: %s", e)
                await ws.send_json({
                    "type": "error",
                    "text": "An error occurred processing your request.",
                })

    try:
        # Attempt to open Deepgram streaming connection
        try:
            dg_connection = await stt_service.create_deepgram_stream(
                _on_transcript
            )
        except Exception as e:
            logger.error("Failed to open Deepgram stream: %s", e)
            await ws.send_json({
                "type": "error",
                "text": "Voice transcription service unavailable.",
            })
            await ws.close()
            return

        # Main loop: pipe browser audio chunks to Deepgram
        while True:
            data = await ws.receive_bytes()
            if dg_connection is not None:
                await dg_connection.send(data)

    except WebSocketDisconnect:
        logger.info("WebRTC WS disconnected — session=%s", session_id)
    except Exception as e:
        logger.error("WebRTC WS error — session=%s: %s", session_id, e)
    finally:
        if dg_connection is not None:
            try:
                await dg_connection.finish()
            except Exception:
                pass
