"""
MediFlow — Redis Session Memory
Used by: Booking Agent (Agent 1)

Handles:
  - Conversation history storage (ephemeral, 30-min TTL)
  - Graceful TTL recovery (agent continues via PostgreSQL lookup)
  - Session ID helpers

Design decision from spec (Section 10 + 13):
  - Redis stores ONLY the last 8 conversation turns
  - PostgreSQL stores all confirmed appointments (permanent)
  - On TTL expiry → agent calls check_patient_history() from PostgreSQL
  - Patient never loses a confirmed booking, only dialogue turns

Usage:
    from services.redis_memory import get_history, save_history, clear_history, RECOVERY_MSG

    history = await get_history(redis_client, session_id)
    await save_history(redis_client, session_id, messages)
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
SESSION_TTL_SECONDS = 1800   # 30 minutes inactivity TTL (per spec)
MAX_HISTORY_TURNS   = 8      # keep last 8 turns in Redis (per spec)

# Key templates — all session keys live under "session:" namespace
def _history_key(session_id: str) -> str:
    return f"session:{session_id}:history"

def _meta_key(session_id: str) -> str:
    return f"session:{session_id}:meta"

# ── Recovery messages (EN + UR) ────────────────────────────────────────────────
# Shown when Redis TTL expired and agent needs to recover context via PostgreSQL
RECOVERY_MSG = {
    "en": "Our session timed out. Let's continue — how can I help you?",
    "ur": "ہماری گفتگو کا وقت ختم ہو گیا۔ آئیں جاری رکھتے ہیں — میں آپ کی کیا مدد کر سکتا ہوں؟",
}

# ── Core memory functions ──────────────────────────────────────────────────────

async def get_history(redis, session_id: str) -> list[dict]:
    """
    Retrieve conversation history from Redis.
    Returns empty list on TTL expiry — this is NOT an error.
    The Booking Agent handles empty history gracefully by calling
    check_patient_history() from PostgreSQL.

    Args:
        redis:      aioredis client instance (injected from FastAPI lifespan)
        session_id: unique session identifier (e.g. "web_abc123", "twilio_CA...")

    Returns:
        list of message dicts: [{"role": "user"|"assistant", "content": "..."}, ...]
    """
    key = _history_key(session_id)
    try:
        raw = await redis.get(key)
        if raw is None:
            logger.debug("Redis miss for session %s (new or expired)", session_id)
            return []
        history = json.loads(raw)
        logger.debug("Redis hit for session %s: %d turns", session_id, len(history))
        return history
    except json.JSONDecodeError:
        logger.warning("Corrupt Redis history for session %s — resetting", session_id)
        await redis.delete(key)
        return []
    except Exception as e:
        # Redis failure should NOT crash the agent — degrade gracefully
        logger.error("Redis get failed for session %s: %s", session_id, e)
        return []


async def save_history(redis, session_id: str, messages: list[dict]) -> None:
    """
    Persist conversation history to Redis.
    Keeps only the last MAX_HISTORY_TURNS turns.
    Refreshes TTL on every message (30-min sliding window).

    Args:
        redis:      aioredis client instance
        session_id: unique session identifier
        messages:   full message list (will be truncated to last 8 turns)
    """
    key = _history_key(session_id)
    try:
        # Trim to last N turns — keeps memory bounded
        trimmed = messages[-MAX_HISTORY_TURNS:]
        payload = json.dumps(trimmed, ensure_ascii=False)

        # setex: set value + expiry in one atomic operation
        await redis.setex(key, SESSION_TTL_SECONDS, payload)
        logger.debug("Saved %d turns for session %s (TTL refreshed)", len(trimmed), session_id)
    except Exception as e:
        # Redis failure must NOT crash the agent — log and continue
        logger.error("Redis save failed for session %s: %s", session_id, e)


async def clear_history(redis, session_id: str) -> None:
    """
    Explicitly clear a session (e.g. after appointment confirmed + patient says goodbye).
    Not strictly required — TTL handles cleanup — but useful for explicit resets.
    """
    key = _history_key(session_id)
    try:
        await redis.delete(key)
        logger.info("Session %s explicitly cleared", session_id)
    except Exception as e:
        logger.error("Redis delete failed for session %s: %s", session_id, e)


async def session_exists(redis, session_id: str) -> bool:
    """
    Check if a session is still alive in Redis.
    Useful for the Booking Agent to decide whether to show a recovery message.
    """
    try:
        return bool(await redis.exists(_history_key(session_id)))
    except Exception:
        return False


async def get_session_ttl(redis, session_id: str) -> Optional[int]:
    """
    Return remaining TTL in seconds. Returns None if key does not exist.
    Useful for debugging / admin dashboard.
    """
    try:
        ttl = await redis.ttl(_history_key(session_id))
        return ttl if ttl > 0 else None
    except Exception:
        return None


# ── Session ID helpers ─────────────────────────────────────────────────────────

def make_session_id(prefix: str = "web") -> str:
    """
    Generate a unique session ID.
    prefix: "web", "twilio", "ws" depending on entry point.

    Examples:
        web_a3f9c2d1
        twilio_CA1234abcd
        ws_b8e7a1f2
    """
    import secrets
    return f"{prefix}_{secrets.token_hex(4)}"


def twilio_session_id(call_sid: str) -> str:
    """Deterministic session ID from Twilio CallSid."""
    return f"twilio_{call_sid}"


def webrtc_session_id(connection_id: str) -> str:
    """Deterministic session ID from WebRTC connection ID."""
    return f"ws_{connection_id}"


# ── How the Booking Agent uses this ───────────────────────────────────────────
#
# class BookingAgent:
#     async def run(self, user_message, session_id, language="en", mode="text"):
#         history = await get_history(self.redis, session_id)
#
#         # On TTL expiry → history is [] but we don't crash
#         # Instead, agent detects empty history + prior context needed
#         # and calls check_patient_history() from PostgreSQL
#
#         messages = history + [{"role": "user", "content": user_message}]
#
#         # ... ReAct loop ...
#
#         messages.append({"role": "assistant", "content": llm_resp.text})
#         await save_history(self.redis, session_id, messages)
#
#         return AgentResponse(message=llm_resp.text, ...)