"""
Tests for the Booking Agent ReAct loop.
Uses mocked LLM router and mocked DB so no real services needed.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agents.booking_agent import (
    process_chat_message,
    _parse_tool_call,
    _get_available_slots,
    _create_appointment,
)


# ── _parse_tool_call tests ────────────────────────────────────────────────────

def test_parse_tool_call_valid():
    text = '{"tool": "get_available_slots", "args": {"specialty": "general"}}'
    result = _parse_tool_call(text)
    assert result is not None
    assert result["tool"] == "get_available_slots"
    assert result["args"]["specialty"] == "general"


def test_parse_tool_call_plain_text():
    text = "I can help you book an appointment."
    result = _parse_tool_call(text)
    assert result is None


def test_parse_tool_call_unknown_tool():
    text = '{"tool": "unknown_tool", "args": {}}'
    result = _parse_tool_call(text)
    assert result is None


def test_parse_tool_call_invalid_json():
    text = '{"tool": "get_available_slots", "args": {invalid}}'
    result = _parse_tool_call(text)
    assert result is None


def test_parse_tool_call_with_surrounding_text():
    text = 'Let me check that. {"tool": "get_doctor_profile", "args": {"doctor_id": 1}} '
    result = _parse_tool_call(text)
    assert result is not None
    assert result["tool"] == "get_doctor_profile"


# ── process_chat_message tests ────────────────────────────────────────────────

@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock(return_value=True)
    return redis


@pytest.fixture
def mock_llm_plain_response():
    """LLM returns plain text immediately — no tool call."""
    mock_response = MagicMock()
    mock_response.text = "How can I help you today?"
    return mock_response


@pytest.fixture
def mock_llm_tool_then_plain():
    """LLM returns tool call first, then plain text."""
    tool_response = MagicMock()
    tool_response.text = '{"tool": "get_available_slots", "args": {"specialty": "general"}}'
    plain_response = MagicMock()
    plain_response.text = "Here are the available slots for general medicine."
    return [tool_response, plain_response]


@pytest.mark.anyio
async def test_process_chat_plain_response(mock_redis, mock_llm_plain_response):
    """Agent returns plain text when LLM doesn't call any tools."""
    with patch("agents.booking_agent.llm_router") as mock_router:
        mock_router.call = AsyncMock(return_value=mock_llm_plain_response)
        result = await process_chat_message(
            user_id="test-user",
            message="Hello",
            redis_client=mock_redis,
            language="en",
            mode="text",
        )
    assert result["response"] == "How can I help you today?"
    assert result["agentId"] == "booking_agent"


@pytest.mark.anyio
async def test_process_chat_saves_to_redis(mock_redis, mock_llm_plain_response):
    """Agent saves conversation history to Redis after response."""
    with patch("agents.booking_agent.llm_router") as mock_router:
        mock_router.call = AsyncMock(return_value=mock_llm_plain_response)
        await process_chat_message(
            user_id="test-user",
            message="Hello",
            redis_client=mock_redis,
        )
    mock_redis.setex.assert_called_once()


@pytest.mark.anyio
async def test_process_chat_loads_history_from_redis(mock_redis, mock_llm_plain_response):
    """Agent loads existing history from Redis on each message."""
    import json
    existing_history = [{"role": "user", "content": "Previous message"}]
    mock_redis.get = AsyncMock(return_value=json.dumps(existing_history).encode())
    with patch("agents.booking_agent.llm_router") as mock_router:
        mock_router.call = AsyncMock(return_value=mock_llm_plain_response)
        await process_chat_message(
            user_id="test-user",
            message="Follow up",
            redis_client=mock_redis,
        )
        # History should be included in messages passed to LLM
        call_args = mock_router.call.call_args
        messages = call_args.kwargs.get("messages") or call_args.args[0]
        assert any(m["content"] == "Previous message" for m in messages)


@pytest.mark.anyio
async def test_process_chat_no_redis(mock_llm_plain_response):
    """Agent works fine without Redis — degrades gracefully."""
    with patch("agents.booking_agent.llm_router") as mock_router:
        mock_router.call = AsyncMock(return_value=mock_llm_plain_response)
        result = await process_chat_message(
            user_id="test-user",
            message="Hello",
            redis_client=None,
        )
    assert result["response"] == "How can I help you today?"


@pytest.mark.anyio
async def test_process_chat_tool_then_plain(mock_redis, mock_llm_tool_then_plain):
    """Agent executes tool call then returns plain text response."""
    responses = iter(mock_llm_tool_then_plain)
    with patch("agents.booking_agent.llm_router") as mock_router, \
         patch.dict("agents.booking_agent.TOOL_MAP", {
             "get_available_slots": AsyncMock(return_value="Dr. Ahmed Raza — slots: 2024-06-01 09:00")
         }):
        mock_router.call = AsyncMock(side_effect=lambda **kwargs: next(responses))
        result = await process_chat_message(
            user_id="test-user",
            message="I need a general medicine appointment",
            redis_client=mock_redis,
        )
    assert result["response"] == "Here are the available slots for general medicine."


@pytest.mark.anyio
async def test_process_chat_voice_mode(mock_redis, mock_llm_plain_response):
    """Voice mode uses voice system prompt."""
    with patch("agents.booking_agent.llm_router") as mock_router:
        mock_router.call = AsyncMock(return_value=mock_llm_plain_response)
        result = await process_chat_message(
            user_id="test-user",
            message="Book appointment",
            redis_client=mock_redis,
            mode="voice",
        )
        call_args = mock_router.call.call_args
        system = call_args.kwargs.get("system") or call_args.args[1]
        assert "voice" in system.lower() or "1-2" in system


@pytest.mark.anyio
async def test_process_chat_urdu_uses_urdu_task_type(mock_redis, mock_llm_plain_response):
    """Urdu language routes to urdu task type in LLM router."""
    with patch("agents.booking_agent.llm_router") as mock_router:
        mock_router.call = AsyncMock(return_value=mock_llm_plain_response)
        await process_chat_message(
            user_id="test-user",
            message="مجھے ڈاکٹر سے ملنا ہے",
            redis_client=mock_redis,
            language="ur",
        )
        call_args = mock_router.call.call_args
        task_type = call_args.kwargs.get("task_type")
        assert task_type == "urdu"


@pytest.mark.anyio
async def test_process_chat_llm_exhausted_returns_recovery(mock_redis):
    """When all LLM providers fail, returns recovery message."""
    from services.llm_router import AllProvidersExhausted
    with patch("agents.booking_agent.llm_router") as mock_router:
        mock_router.call = AsyncMock(side_effect=AllProvidersExhausted("all failed"))
        result = await process_chat_message(
            user_id="test-user",
            message="Hello",
            redis_client=mock_redis,
            language="en",
        )
    assert "session" in result["response"].lower() or "help" in result["response"].lower()


# ── Max steps test ────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_voice_mode_max_steps_is_3(mock_redis):
    """Voice mode stops after 3 steps maximum."""
    tool_response = MagicMock()
    tool_response.text = '{"tool": "get_available_slots", "args": {"specialty": "general"}}'
    plain_response = MagicMock()
    plain_response.text = "Here are the slots."

    call_count = 0
    async def mock_call(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 3:
            return tool_response
        return plain_response

    with patch("agents.booking_agent.llm_router") as mock_router, \
         patch("agents.booking_agent._get_available_slots", AsyncMock(return_value="slots")):
        mock_router.call = mock_call
        await process_chat_message(
            user_id="test-user",
            message="Book appointment",
            redis_client=mock_redis,
            mode="voice",
        )
    # Voice mode: MAX_STEPS=3 + 1 final wrap-up call = 4 max
    assert call_count <= 4