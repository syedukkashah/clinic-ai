"""
STT Service (v5.0)
==================

Deepgram Nova-3 Speech-to-Text with a three-tier fallback chain:

1. **Deepgram Nova-3** (primary) — streaming and file/REST modes
2. **Groq Whisper-large-v3** — if Deepgram is unavailable
3. **Local Whisper small** — lazy-loaded last resort

Prometheus metrics are emitted on every call.
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import time
from typing import Any, Callable, Dict, Optional

from prometheus_client import Counter, Histogram

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "")

# ---------------------------------------------------------------------------
# Prometheus metrics (names mandated by AIOps team — M6)
# ---------------------------------------------------------------------------

PROM_STT_CALLS = Counter(
    "mediflow_stt_calls_total",
    "Total STT transcription calls",
    ["provider", "lang"],
)
PROM_STT_LAT = Histogram(
    "mediflow_stt_latency_seconds",
    "STT transcription latency in seconds",
)
PROM_URDISH_RATE = Counter(
    "mediflow_urdish_detection_total",
    "Transcripts detected as mixed Urdu-English",
    ["detected_as"],
)

# ---------------------------------------------------------------------------
# Lazy-loaded local Whisper fallback
# ---------------------------------------------------------------------------

_local_whisper = None


def _get_local_whisper():
    """Lazy-load the local Whisper model (small). Never imported at module level."""
    global _local_whisper
    if _local_whisper is None:
        import whisper  # noqa: F811 — intentional lazy import
        _local_whisper = whisper.load_model("small")
    return _local_whisper


# ---------------------------------------------------------------------------
# File / REST mode — for HTTP voice note uploads
# ---------------------------------------------------------------------------

async def transcribe_file(audio_bytes: bytes) -> Dict[str, str]:
    """
    Transcribe an audio file using the Deepgram Nova-3 REST API.

    Falls back to Groq Whisper, then to local Whisper if Deepgram fails.

    Args:
        audio_bytes: Raw audio content (webm, wav, mp3, etc.).

    Returns:
        ``{"transcript": str, "lang": str}`` where lang is ``"en"`` or ``"ur"``.
    """
    t0 = time.time()

    # --- Attempt 1: Deepgram Nova-3 ---
    if DEEPGRAM_API_KEY:
        try:
            result = await _transcribe_deepgram(audio_bytes)
            elapsed = time.time() - t0
            PROM_STT_CALLS.labels(provider="deepgram_nova3", lang=result["lang"]).inc()
            PROM_STT_LAT.observe(elapsed)
            _record_urdish(result["lang"])
            return result
        except Exception as e:
            logger.warning("Deepgram STT failed, falling back: %s", e)

    # --- Attempt 2: Groq Whisper ---
    try:
        result = await _transcribe_groq(audio_bytes)
        elapsed = time.time() - t0
        PROM_STT_CALLS.labels(provider="groq_whisper", lang=result["lang"]).inc()
        PROM_STT_LAT.observe(elapsed)
        _record_urdish(result["lang"])
        return result
    except Exception as e:
        logger.warning("Groq Whisper STT failed, falling back to local: %s", e)

    # --- Attempt 3: Local Whisper (last resort) ---
    try:
        result = await _transcribe_local_whisper(audio_bytes)
        elapsed = time.time() - t0
        PROM_STT_CALLS.labels(provider="local_whisper", lang=result["lang"]).inc()
        PROM_STT_LAT.observe(elapsed)
        _record_urdish(result["lang"])
        return result
    except Exception as e:
        logger.error("All STT providers failed: %s", e)
        # Return empty transcript — caller handles canned response
        return {"transcript": "", "lang": "en"}


async def _transcribe_deepgram(audio_bytes: bytes) -> Dict[str, str]:
    """Transcribe audio using Deepgram Nova-3 REST API."""
    from deepgram import DeepgramClient, PrerecordedOptions

    dg = DeepgramClient(DEEPGRAM_API_KEY)
    options = PrerecordedOptions(
        model="nova-3",
        language="multi",
        smart_format=True,
        punctuate=True,
    )
    response = await dg.listen.asyncrest.v("1").transcribe_file(
        {"buffer": audio_bytes, "mimetype": "audio/webm"},
        options,
    )
    transcript = response.results.channels[0].alternatives[0].transcript
    detected_lang = getattr(
        response.results.channels[0], "detected_language", None
    )
    lang = _normalize_lang(detected_lang)
    return {"transcript": transcript or "", "lang": lang}


async def _transcribe_groq(audio_bytes: bytes) -> Dict[str, str]:
    """Transcribe audio using Groq Whisper-large-v3."""
    from groq import AsyncGroq

    groq_keys = os.environ.get("GROQ_API_KEYS", "")
    keys = [k.strip() for k in groq_keys.split(",") if k.strip()]
    if not keys:
        raise RuntimeError("No GROQ_API_KEYS available for Whisper fallback")

    # Write audio to a temp file — Groq SDK needs a file-like object
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        client = AsyncGroq(api_key=keys[0])
        with open(tmp_path, "rb") as f:
            transcription = await client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=f,
                language="ur",  # Groq Whisper handles both en/ur; setting ur for best Urdu results
            )
        transcript = transcription.text or ""
        lang = _detect_lang_heuristic(transcript)
        return {"transcript": transcript, "lang": lang}
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


async def _transcribe_local_whisper(audio_bytes: bytes) -> Dict[str, str]:
    """Transcribe audio using local Whisper model (lazy-loaded)."""
    # Write to temp file
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        model = _get_local_whisper()
        # Run in executor to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, lambda: model.transcribe(tmp_path)
        )
        transcript = result.get("text", "")
        detected = result.get("language", "en")
        lang = "ur" if detected in ("ur", "urdu") else "en"
        return {"transcript": transcript, "lang": lang}
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Streaming mode — for WebRTC WebSocket
# ---------------------------------------------------------------------------

async def create_deepgram_stream(on_transcript: Callable) -> Any:
    """
    Create a Deepgram live streaming connection for real-time transcription.

    Args:
        on_transcript: Async callback ``(sentence, lang, is_final) -> None``
            called for each partial or final transcript.

    Returns:
        A Deepgram ``LiveConnection`` object. The caller manages its lifecycle.

    Raises:
        Exception: If Deepgram connection cannot be established.
    """
    from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents

    dg = DeepgramClient(DEEPGRAM_API_KEY)
    connection = dg.listen.asyncwebsocket.v("1")

    async def _on_message(self, result, **kwargs):
        """Handle incoming transcript from Deepgram WebSocket."""
        sentence = result.channel.alternatives[0].transcript
        if not sentence:
            return
        lang = _normalize_lang(
            getattr(result.channel, "detected_language", None)
        )
        is_final = result.is_final
        await on_transcript(sentence, lang, is_final)

    connection.on(LiveTranscriptionEvents.Transcript, _on_message)

    options = LiveOptions(
        model="nova-3",
        language="multi",
        smart_format=True,
        punctuate=True,
        interim_results=True,
        utterance_end_ms=1000,
    )
    await connection.start(options)
    return connection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_lang(detected: Optional[str]) -> str:
    """Normalize Deepgram's detected_language to 'en' or 'ur'."""
    if detected and detected.lower().startswith("ur"):
        return "ur"
    return "en"


def _detect_lang_heuristic(text: str) -> str:
    """Heuristic language detection for fallback paths (no Deepgram metadata)."""
    urdu_chars = set("ابپتٹثجچحخدڈذرڑزژسشصضطظعغفقکگلمنوہھیے")
    urdu_count = sum(1 for ch in text if ch in urdu_chars)
    return "ur" if urdu_count > len(text) * 0.3 else "en"


def _record_urdish(lang: str) -> None:
    """Record language detection for M6 Urdish drift analysis."""
    PROM_URDISH_RATE.labels(detected_as=lang).inc()
