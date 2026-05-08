'EOF'
"""
Test suite for services/redis_memory.py
Uses a REAL Redis instance (via pytest fixture).
In CI: Redis service container on redis://localhost:6379
Locally: Redis running in Docker on redis://localhost:6379

Run with:
    pytest tests/test_redis_memory.py -v
"""

import pytest
import pytest_asyncio
import redis.asyncio as aioredis

from services.redis_memory import (
    get_history,
    save_history,
    clear_history,
    session_exists,
    get_session_ttl,
    make_session_id,
    twilio_session_id,
    webrtc_session_id,
    RECOVERY_MSG,
    MAX_HISTORY_TURNS,
    SESSION_TTL_SECONDS,
)

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def redis():
    """
    Real Redis client connected to redis://localhost:6379
    Each test gets a clean slate — all keys flushed after test.
    """
    r = await aioredis.from_url("redis://localhost:6379", decode_responses=True)
    await r.flushdb()  # clean before test
    yield r
    await r.flushdb()  # clean after test
    await r.aclose()


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_empty_history_on_new_session(redis):
    history = await get_history(redis, "session_abc")
    assert history == []
    assert isinstance(history, list)


@pytest.mark.asyncio
async def test_save_and_retrieve(redis):
    messages = [
        {"role": "user",      "content": "I need a doctor tomorrow"},
        {"role": "assistant", "content": "Sure! What specialty do you need?"},
        {"role": "user",      "content": "General physician"},
    ]
    await save_history(redis, "session_abc", messages)
    retrieved = await get_history(redis, "session_abc")

    assert len(retrieved) == 3
    assert retrieved[0]["role"] == "user"
    assert retrieved[-1]["content"] == "General physician"


@pytest.mark.asyncio
async def test_ttl_is_set(redis):
    messages = [{"role": "user", "content": "Hello"}]
    await save_history(redis, "session_abc", messages)
    ttl = await get_session_ttl(redis, "session_abc")

    assert ttl is not None
    assert ttl == SESSION_TTL_SECONDS or ttl == SESSION_TTL_SECONDS - 1  # allow 1s drift


@pytest.mark.asyncio
async def test_max_history_trim(redis):
    messages = [{"role": "user", "content": f"Message {i}"} for i in range(12)]
    await save_history(redis, "session_abc", messages)
    retrieved = await get_history(redis, "session_abc")

    assert len(retrieved) == MAX_HISTORY_TURNS
    assert retrieved[-1]["content"] == "Message 11"
    assert retrieved[0]["content"] == "Message 4"


@pytest.mark.asyncio
async def test_ttl_expiry_recovery(redis):
    """Real TTL expiry — set a 1 second TTL and wait for it to expire."""
    import asyncio
    import json

    # Manually set key with 1 second TTL
    await redis.setex("session:session_xyz:history",
                      1,
                      json.dumps([{"role": "user", "content": "Book me a slot"}]))

    await asyncio.sleep(2)  # wait for real expiry

    history = await get_history(redis, "session_xyz")
    assert history == []


@pytest.mark.asyncio
async def test_session_exists(redis):
    messages = [{"role": "user", "content": "Hello"}]
    await save_history(redis, "session_live", messages)

    assert await session_exists(redis, "session_live") is True
    assert await session_exists(redis, "session_new") is False


@pytest.mark.asyncio
async def test_clear_history(redis):
    messages = [{"role": "user", "content": "Cancel my appointment"}]
    await save_history(redis, "session_abc", messages)
    await clear_history(redis, "session_abc")

    history = await get_history(redis, "session_abc")
    assert history == []
    assert await session_exists(redis, "session_abc") is False


@pytest.mark.asyncio
async def test_corrupt_data_recovery(redis):
    """Manually write garbage JSON — get_history must handle it gracefully."""
    await redis.setex("session:session_corrupt:history", 1800, "NOT_VALID_JSON{{{{")
    history = await get_history(redis, "session_corrupt")
    assert history == []


@pytest.mark.asyncio
async def test_redis_failure_does_not_crash():
    """No real Redis needed — tests graceful degradation on connection failure."""

    class BrokenRedis:
        async def get(self, key):
            raise ConnectionError("Redis is down")
        async def setex(self, key, ttl, value):
            raise ConnectionError("Redis is down")
        async def delete(self, key):
            raise ConnectionError("Redis is down")
        async def exists(self, key):
            raise ConnectionError("Redis is down")
        async def ttl(self, key):
            raise ConnectionError("Redis is down")

    broken = BrokenRedis()
    history = await get_history(broken, "session_abc")
    assert history == []

    # Must not raise
    await save_history(broken, "session_abc", [{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_recovery_messages():
    assert bool(RECOVERY_MSG.get("en"))
    assert bool(RECOVERY_MSG.get("ur"))
    assert len(RECOVERY_MSG["en"]) > 10
    assert len(RECOVERY_MSG["ur"]) > 10


@pytest.mark.asyncio
async def test_session_id_helpers():
    sid = make_session_id("web")
    assert sid.startswith("web_")
    assert make_session_id("web") != make_session_id("web")
    assert twilio_session_id("CA1234abcd") == "twilio_CA1234abcd"
    assert webrtc_session_id("conn_9f8a") == "ws_conn_9f8a"


@pytest.mark.asyncio
async def test_urdu_content_preserved(redis):
    urdu_msg = "مجھے کل صبح ڈاکٹر سے ملنا ہے"
    messages = [{"role": "user", "content": urdu_msg}]
    await save_history(redis, "session_ur", messages)
    retrieved = await get_history(redis, "session_ur")
    assert retrieved[0]["content"] == urdu_msg


@pytest.mark.asyncio
async def test_multiple_sessions_isolated(redis):
    msgs_a = [{"role": "user", "content": "Session A message"}]
    msgs_b = [{"role": "user", "content": "Session B message"}]
    await save_history(redis, "session_a", msgs_a)
    await save_history(redis, "session_b", msgs_b)

    hist_a = await get_history(redis, "session_a")
    hist_b = await get_history(redis, "session_b")

    assert hist_a[0]["content"] == "Session A message"
    assert hist_b[0]["content"] == "Session B message"
    assert hist_a != hist_b

    await clear_history(redis, "session_a")
    assert await get_history(redis, "session_b") == msgs_b


@pytest.mark.asyncio
async def test_booking_agent_flow_simulation(redis):
    session = "web_patient_001"

    turn1 = [{"role": "user", "content": "I need a cardiologist"}]
    await save_history(redis, session, turn1)

    turn2 = turn1 + [{"role": "assistant", "content": "I found 3 cardiologists. Which date?"}]
    await save_history(redis, session, turn2)

    turn3 = turn2 + [{"role": "user", "content": "Tomorrow morning"}]
    await save_history(redis, session, turn3)

    turn4 = turn3 + [{"role": "assistant", "content": "Confirmed! Dr. Khan at 10am tomorrow."}]
    await save_history(redis, session, turn4)

    history = await get_history(redis, session)
    assert len(history) == 4
    assert [m["role"] for m in history] == ["user", "assistant", "user", "assistant"]
    assert "Confirmed" in history[-1]["content"]
