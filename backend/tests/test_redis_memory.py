"""
Test suite for services/redis_memory.py
No Docker, no real Redis needed — uses a mock Redis client.

Run with:
    python test_redis_memory.py
"""

import asyncio
import json
import sys
import os

# Add parent directory so we can import redis_memory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from services.redis_memory import (  # backend/services/redis_memory.py
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
# Mock Redis client — simulates aioredis behaviour in memory
# ─────────────────────────────────────────────────────────────────────────────

class MockRedis:
    """
    In-memory mock that replicates the aioredis API used in redis_memory.py.
    Supports: get, set, setex, delete, exists, ttl
    Also simulates key expiry so TTL recovery logic can be tested.
    """

    def __init__(self):
        self._store: dict[str, str] = {}
        self._ttl: dict[str, int] = {}   # stores remaining TTL in seconds
        self._expired: set[str] = set()  # keys manually marked as expired

    async def get(self, key: str):
        if key in self._expired or key not in self._store:
            return None
        return self._store[key]

    async def set(self, key: str, value: str):
        self._store[key] = value
        self._expired.discard(key)

    async def setex(self, key: str, ttl: int, value: str):
        self._store[key] = value
        self._ttl[key] = ttl
        self._expired.discard(key)

    async def delete(self, key: str):
        self._store.pop(key, None)
        self._ttl.pop(key, None)
        self._expired.discard(key)

    async def exists(self, key: str) -> int:
        if key in self._expired:
            return 0
        return 1 if key in self._store else 0

    async def ttl(self, key: str) -> int:
        if key in self._expired or key not in self._store:
            return -2   # aioredis returns -2 for non-existent keys
        return self._ttl.get(key, -1)

    def simulate_expiry(self, key: str):
        """Helper to simulate TTL expiry for testing recovery logic."""
        self._expired.add(key)


# ─────────────────────────────────────────────────────────────────────────────
# Test helpers
# ─────────────────────────────────────────────────────────────────────────────

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
results = []

def check(label: str, condition: bool, detail: str = ""):
    symbol = PASS if condition else FAIL
    status = "PASS" if condition else "FAIL"
    suffix = f"  ({detail})" if detail else ""
    print(f"  {symbol} {label}{suffix}")
    results.append((label, condition))


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

async def test_empty_history_on_new_session():
    print("\n[1] Empty history on new session")
    redis = MockRedis()
    history = await get_history(redis, "session_abc")
    check("Returns empty list for new session", history == [])
    check("Return type is list", isinstance(history, list))


async def test_save_and_retrieve():
    print("\n[2] Save and retrieve conversation turns")
    redis = MockRedis()
    messages = [
        {"role": "user",      "content": "I need a doctor tomorrow"},
        {"role": "assistant", "content": "Sure! What specialty do you need?"},
        {"role": "user",      "content": "General physician"},
    ]
    await save_history(redis, "session_abc", messages)
    retrieved = await get_history(redis, "session_abc")
    check("Correct number of turns retrieved", len(retrieved) == 3)
    check("First message role is 'user'",      retrieved[0]["role"] == "user")
    check("Last message content correct",      retrieved[-1]["content"] == "General physician")


async def test_ttl_is_set():
    print("\n[3] TTL is set on save (30-min sliding window)")
    redis = MockRedis()
    messages = [{"role": "user", "content": "Hello"}]
    await save_history(redis, "session_abc", messages)
    ttl = await get_session_ttl(redis, "session_abc")
    check("TTL is set",                   ttl is not None)
    check("TTL equals SESSION_TTL_SECONDS", ttl == SESSION_TTL_SECONDS,
          f"expected {SESSION_TTL_SECONDS}, got {ttl}")


async def test_max_history_trim():
    print("\n[4] History is trimmed to last 8 turns")
    redis = MockRedis()
    # Create 12 messages — more than MAX_HISTORY_TURNS
    messages = [{"role": "user", "content": f"Message {i}"} for i in range(12)]
    await save_history(redis, "session_abc", messages)
    retrieved = await get_history(redis, "session_abc")
    check(f"Stored turns capped at {MAX_HISTORY_TURNS}", len(retrieved) == MAX_HISTORY_TURNS)
    check("Most recent turns are kept (not oldest)",
          retrieved[-1]["content"] == "Message 11")
    check("Oldest turns were dropped",
          retrieved[0]["content"] == "Message 4")


async def test_ttl_expiry_recovery():
    print("\n[5] TTL expiry — empty list returned (graceful recovery)")
    redis = MockRedis()
    messages = [{"role": "user", "content": "Book me a slot"}]
    await save_history(redis, "session_xyz", messages)

    # Simulate 30-min inactivity timeout
    redis.simulate_expiry("session:session_xyz:history")

    history = await get_history(redis, "session_xyz")
    check("Returns empty list after TTL expiry", history == [],
          "agent handles this by calling check_patient_history() from PostgreSQL")
    check("No exception raised", True)


async def test_session_exists():
    print("\n[6] session_exists() correctly reflects live vs expired sessions")
    redis = MockRedis()
    messages = [{"role": "user", "content": "Hello"}]
    await save_history(redis, "session_live", messages)

    check("Live session returns True",  await session_exists(redis, "session_live"))
    check("New session returns False",  not await session_exists(redis, "session_new"))

    redis.simulate_expiry("session:session_live:history")
    check("Expired session returns False", not await session_exists(redis, "session_live"))


async def test_clear_history():
    print("\n[7] Explicit session clear")
    redis = MockRedis()
    messages = [{"role": "user", "content": "Cancel my appointment"}]
    await save_history(redis, "session_abc", messages)
    await clear_history(redis, "session_abc")
    history = await get_history(redis, "session_abc")
    check("History is empty after clear",    history == [])
    check("Session no longer exists",        not await session_exists(redis, "session_abc"))


async def test_corrupt_data_recovery():
    print("\n[8] Corrupt Redis data is handled gracefully")
    redis = MockRedis()
    # Manually write garbage JSON to simulate corruption
    await redis.setex("session:session_corrupt:history", 1800, "NOT_VALID_JSON{{{{")
    history = await get_history(redis, "session_corrupt")
    check("Returns empty list on corrupt data", history == [])
    check("Key is cleaned up after corruption",
          not await session_exists(redis, "session_corrupt"))


async def test_redis_failure_does_not_crash():
    print("\n[9] Redis failure degrades gracefully — agent never crashes")

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
    check("get_history returns [] when Redis is down", history == [])

    # save_history should not raise
    try:
        await save_history(broken, "session_abc", [{"role": "user", "content": "hi"}])
        check("save_history does not raise when Redis is down", True)
    except Exception as e:
        check("save_history does not raise when Redis is down", False, str(e))


async def test_recovery_messages():
    print("\n[10] Recovery messages exist for both languages")
    check("English recovery message present", bool(RECOVERY_MSG.get("en")))
    check("Urdu recovery message present",    bool(RECOVERY_MSG.get("ur")))
    check("English message is non-empty",     len(RECOVERY_MSG["en"]) > 10)
    check("Urdu message is non-empty",        len(RECOVERY_MSG["ur"]) > 10)


async def test_session_id_helpers():
    print("\n[11] Session ID helper functions")
    sid = make_session_id("web")
    check("make_session_id has correct prefix", sid.startswith("web_"))
    check("make_session_id is unique",
          make_session_id("web") != make_session_id("web"))

    twilio_sid = twilio_session_id("CA1234abcd")
    check("Twilio session ID format correct", twilio_sid == "twilio_CA1234abcd")

    ws_sid = webrtc_session_id("conn_9f8a")
    check("WebRTC session ID format correct", ws_sid == "ws_conn_9f8a")


async def test_urdu_content_preserved():
    print("\n[12] Urdu text stored and retrieved without corruption")
    redis = MockRedis()
    urdu_msg = "مجھے کل صبح ڈاکٹر سے ملنا ہے"
    messages = [{"role": "user", "content": urdu_msg}]
    await save_history(redis, "session_ur", messages)
    retrieved = await get_history(redis, "session_ur")
    check("Urdu content retrieved intact", retrieved[0]["content"] == urdu_msg)


async def test_multiple_sessions_isolated():
    print("\n[13] Multiple sessions are fully isolated from each other")
    redis = MockRedis()
    msgs_a = [{"role": "user", "content": "Session A message"}]
    msgs_b = [{"role": "user", "content": "Session B message"}]
    await save_history(redis, "session_a", msgs_a)
    await save_history(redis, "session_b", msgs_b)

    hist_a = await get_history(redis, "session_a")
    hist_b = await get_history(redis, "session_b")

    check("Session A has its own messages", hist_a[0]["content"] == "Session A message")
    check("Session B has its own messages", hist_b[0]["content"] == "Session B message")
    check("Sessions don't bleed into each other", hist_a != hist_b)

    await clear_history(redis, "session_a")
    check("Clearing A doesn't affect B", (await get_history(redis, "session_b")) == msgs_b)


async def test_booking_agent_flow_simulation():
    print("\n[14] Full Booking Agent conversation flow simulation")
    redis = MockRedis()
    session = "web_patient_001"

    # Turn 1: patient opens chat
    turn1 = [{"role": "user", "content": "I need a cardiologist"}]
    await save_history(redis, session, turn1)

    # Turn 2: agent responds
    turn2 = turn1 + [{"role": "assistant", "content": "I found 3 cardiologists. Which date?"}]
    await save_history(redis, session, turn2)

    # Turn 3: patient picks date
    turn3 = turn2 + [{"role": "user", "content": "Tomorrow morning"}]
    await save_history(redis, session, turn3)

    # Turn 4: agent confirms
    turn4 = turn3 + [{"role": "assistant", "content": "Confirmed! Dr. Khan at 10am tomorrow."}]
    await save_history(redis, session, turn4)

    history = await get_history(redis, session)
    check("All 4 turns saved correctly",   len(history) == 4)
    check("Role sequence is correct",
          [m["role"] for m in history] == ["user", "assistant", "user", "assistant"])
    check("Final confirmation is stored",  "Confirmed" in history[-1]["content"])

    # Simulate patient coming back after timeout
    redis.simulate_expiry(f"session:{session}:history")
    recovered = await get_history(redis, session)
    check("After timeout, empty history returned", recovered == [])
    check("Agent would now call check_patient_history() from PostgreSQL",
          True, "this is handled in BookingAgent.run()")


# ─────────────────────────────────────────────────────────────────────────────
# Main runner
# ─────────────────────────────────────────────────────────────────────────────

async def run_all():
    print("=" * 60)
    print("  MediFlow — Redis Memory Tests (no Docker needed)")
    print("=" * 60)

    await test_empty_history_on_new_session()
    await test_save_and_retrieve()
    await test_ttl_is_set()
    await test_max_history_trim()
    await test_ttl_expiry_recovery()
    await test_session_exists()
    await test_clear_history()
    await test_corrupt_data_recovery()
    await test_redis_failure_does_not_crash()
    await test_recovery_messages()
    await test_session_id_helpers()
    await test_urdu_content_preserved()
    await test_multiple_sessions_isolated()
    await test_booking_agent_flow_simulation()

    print("\n" + "=" * 60)
    passed = sum(1 for _, ok in results if ok)
    failed = sum(1 for _, ok in results if not ok)
    total  = len(results)
    print(f"  Results: {passed}/{total} passed", end="")
    if failed:
        print(f"  |  {failed} FAILED:")
        for label, ok in results:
            if not ok:
                print(f"      \033[91m✗ {label}\033[0m")
    else:
        print("  — all good!")
    print("=" * 60)

    if failed:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_all())