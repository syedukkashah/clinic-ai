"""
TTS Service (v5.0)
==================

Language-branching Text-to-Speech:

- **English** → Deepgram Aura-2 REST API (``aura-2-en-us``)
- **Urdu** → Edge TTS (``ur-PK-UzmaNeural``)

Both paths write audio to a file and return the output path.
Prometheus TTFB metric emitted on every synthesis call.
"""

from __future__ import annotations

import logging
import os
import time

import edge_tts
import httpx
from prometheus_client import Histogram

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "")

# ---------------------------------------------------------------------------
# Prometheus metrics (name mandated by AIOps team — M6)
# ---------------------------------------------------------------------------

PROM_TTS_TTFB = Histogram(
    "mediflow_tts_ttfb_seconds",
    "TTS time-to-first-byte in seconds",
    ["provider"],
    buckets=[0.1, 0.2, 0.3, 0.5, 1.0, 1.5, 2.0],
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def synthesize(text: str, lang: str, out_path: str) -> str:
    """
    Synthesize speech from text, routing by language.

    Args:
        text: The text to speak.
        lang: Language code — ``"en"`` routes to Aura-2, ``"ur"`` to Edge TTS.
        out_path: Filesystem path to write the output audio (MP3).

    Returns:
        The ``out_path`` that was written to.
    """
    if lang == "ur":
        return await _synthesize_edge(text, out_path)
    else:
        return await _synthesize_aura(text, out_path)


# ---------------------------------------------------------------------------
# Deepgram Aura-2 (English)
# ---------------------------------------------------------------------------

async def _synthesize_aura(text: str, out_path: str) -> str:
    """
    Synthesize English speech using Deepgram Aura-2.

    Falls back to Edge TTS ``en-US-JennyNeural`` on any HTTP error.
    """
    t0 = time.time()
    url = "https://api.deepgram.com/v1/speak"
    params = {"model": "aura-2-en-us"}
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                params=params,
                headers=headers,
                json={"text": text},
            )
            resp.raise_for_status()

        ttfb = time.time() - t0
        PROM_TTS_TTFB.labels(provider="deepgram_aura2").observe(ttfb)

        # Ensure parent directory exists
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(resp.content)

        return out_path

    except (httpx.HTTPError, httpx.HTTPStatusError) as e:
        logger.warning("Deepgram Aura-2 TTS failed, falling back to Edge TTS: %s", e)
        return await _synthesize_edge(text, out_path, voice="en-US-JennyNeural")


# ---------------------------------------------------------------------------
# Edge TTS (Urdu — or English fallback)
# ---------------------------------------------------------------------------

async def _synthesize_edge(
    text: str,
    out_path: str,
    voice: str = "ur-PK-UzmaNeural",
) -> str:
    """
    Synthesize speech using Microsoft Edge TTS.

    Args:
        text: Text to speak.
        out_path: Output file path.
        voice: Edge TTS voice identifier.

    Returns:
        The ``out_path`` that was written to.
    """
    t0 = time.time()

    # Ensure parent directory exists
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    await edge_tts.Communicate(text, voice).save(out_path)

    ttfb = time.time() - t0
    PROM_TTS_TTFB.labels(provider="edge_tts").observe(ttfb)

    return out_path
