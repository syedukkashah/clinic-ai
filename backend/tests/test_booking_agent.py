"""
Tests for the Booking Agent ReAct loop.
Uses mocked LLM router and mocked DB so no real services needed.
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from agents.booking_agent import (
    process_chat_message,
    _parse_tool_call,
    _get_available_slots,
    _create_appointment,
    _cancel_appointment,
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


def test_parse_tool_call_normalizes_aliases():
    text = '{"tool": "list_doctors", "args": {"specialization": "Cardiologists"}}'
    result = _parse_tool_call(text)
    assert result is not None
    assert result["tool"] == "list_doctors"
    assert result["args"]["specialty"] == "cardiology"


def test_voice_prompt_has_patient_facing_guardrails():
    from agents.booking_agent import PROMPT_VOICE

    assert "Never speak JSON" in PROMPT_VOICE
    assert "Do not create an appointment until" in PROMPT_VOICE


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


class FakeRedis:
    def __init__(self):
        self.store = {}

    async def get(self, key):
        return self.store.get(key)

    async def setex(self, key, ttl, value):
        self.store[key] = value

    async def delete(self, key):
        self.store.pop(key, None)

    async def exists(self, key):
        return key in self.store


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
async def test_process_chat_suppresses_unknown_tool_json(mock_redis):
    """Unknown model tool calls must never leak raw JSON to patients."""
    mock_response = MagicMock()
    mock_response.text = '{"tool": "unknown_tool", "args": {}}'
    with patch("agents.booking_agent.llm_router") as mock_router:
        mock_router.call = AsyncMock(return_value=mock_response)
        result = await process_chat_message(
            user_id="test-user",
            message="clinic timings",
            redis_client=mock_redis,
        )
    assert '{"tool"' not in result["response"]
    assert "more detail" in result["response"].lower()


@pytest.mark.anyio
async def test_create_appointment_requires_missing_details():
    """The tool must ask for missing patient details instead of creating fake appointments."""
    result = await _create_appointment({
        "doctor_id": 1,
        "appointment_date": "2026-05-13",
        "appointment_time": "09:00",
        "reason": "General Check-up",
    })
    assert "full name" in result.lower()


@pytest.mark.anyio
async def test_booking_state_completes_after_contact_number():
    """A realistic booking conversation should preserve state and confirm after phone."""
    redis = FakeRedis()
    session_id = "patient-session"

    with patch("agents.booking_agent._list_doctors", AsyncMock(return_value="Available doctors:\nDr. Kamran Iqbal (ID 3), General Practice")), \
         patch("agents.booking_agent._create_appointment", AsyncMock(return_value="Appointment confirmed! ID: apt-test. Date: 2026-05-18 at 08:00.")) as mock_create:
        first = await process_chat_message(
            user_id=session_id,
            message="i want to book an appointment. I have flu. which doctors are available",
            redis_client=redis,
        )
        assert "Kamran" in first["response"]

        second = await process_chat_message(
            user_id=session_id,
            message="My name is rayyan, I have fever and cold. I want to visit doctor kamran on monday at 8 am",
            redis_client=redis,
        )
        assert "contact number" in second["response"].lower()

        final = await process_chat_message(
            user_id=session_id,
            message="03352034811",
            redis_client=redis,
        )

    assert "Appointment confirmed" in final["response"]
    args = mock_create.await_args.args[0]
    assert args["patient_name"] == "Rayyan"
    assert args["doctor_id"] == 3
    assert args["time"] == "08:00"
    assert args["contact_number"] == "03352034811"


@pytest.mark.anyio
async def test_booking_state_accepts_comma_separated_details():
    """Patient can provide name, department, natural date, time, reason, and phone in one message."""
    redis = FakeRedis()
    session_id = "patient-comma-session"

    with patch("agents.booking_agent._create_appointment", AsyncMock(return_value="Appointment confirmed! ID: apt-comma. Date: 2026-06-06 at 16:00.")) as mock_create:
        first = await process_chat_message(
            user_id=session_id,
            message="Book an appointment",
            redis_client=redis,
        )
        assert "full name" in first["response"].lower()

        final = await process_chat_message(
            user_id=session_id,
            message="riya, dermatologist, 6th june 2026, 4pm, general, 0321399012",
            redis_client=redis,
        )

    assert "Appointment confirmed" in final["response"]
    args = mock_create.await_args.args[0]
    assert args["patient_name"] == "Riya"
    assert args["doctor_id"] == 8
    assert args["doctor_name"] == "Zara Siddiqui"
    assert args["date"] == "2026-06-06"
    assert args["time"] == "16:00"
    assert args["complaint"] == "general"
    assert args["contact_number"] == "0321399012"


@pytest.mark.anyio
async def test_booking_state_can_be_paused_without_looping():
    """Short escape phrases should clear stale booking state instead of repeating missing fields."""
    redis = FakeRedis()
    session_id = "patient-stale-booking"

    first = await process_chat_message(
        user_id=session_id,
        message="Book an appointment",
        redis_client=redis,
    )
    assert "which doctor" in first["response"].lower()

    paused = await process_chat_message(
        user_id=session_id,
        message="nvm",
        redis_client=redis,
    )

    assert "paused" in paused["response"].lower()
    assert "which doctor or department" not in paused["response"].lower()


@pytest.mark.anyio
async def test_reschedule_flow_does_not_create_new_appointment():
    """Reschedule intent should not fall into create_appointment missing-field prompts."""
    redis = FakeRedis()
    session_id = "patient-reschedule-session"

    with patch("agents.booking_agent._create_appointment", AsyncMock()) as mock_create, \
         patch("agents.booking_agent._reschedule_appointment", AsyncMock(return_value="Appointment apt-123 rescheduled successfully. New date: 2026-05-19 at 11:00.")) as mock_reschedule:
        first = await process_chat_message(
            user_id=session_id,
            message="hello, I need to reschedule an appointment",
            redis_client=redis,
        )
        assert "appointment id" in first["response"].lower()

        second = await process_chat_message(
            user_id=session_id,
            message="doctor sara, ID: apt-123. Date: 2026-05-18 at 10:00.",
            redis_client=redis,
        )
        assert "new appointment date" in second["response"].lower()
        assert "reason for visit" not in second["response"].lower()

        final = await process_chat_message(
            user_id=session_id,
            message="move it to 2026-05-19 at 11:00",
            redis_client=redis,
        )

    mock_create.assert_not_called()
    mock_reschedule.assert_awaited_once()
    args = mock_reschedule.await_args.args[0]
    assert args["appointment_id"] == "apt-123"
    assert args["date"] == "2026-05-19"
    assert args["time"] == "11:00"
    assert "rescheduled successfully" in final["response"]


@pytest.mark.anyio
async def test_cancel_appointment_commits_on_success():
    """Cancelling through the agent-owned session should persist the delete."""
    class FakeSession:
        def __init__(self):
            self.committed = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def commit(self):
            self.committed = True

    fake_session = FakeSession()
    with patch("agents.booking_agent.AsyncSessionLocal", return_value=fake_session), patch(
        "agents.booking_agent.crud.delete_appointment",
        AsyncMock(return_value=True),
    ) as mock_delete:
        result = await _cancel_appointment({"appointment_id": "apt-123"})

    mock_delete.assert_awaited_once_with(fake_session, "apt-123")
    assert fake_session.committed is True
    assert "cancelled" in result.lower()


@pytest.mark.anyio
async def test_process_chat_tool_then_plain(mock_redis, mock_llm_tool_then_plain):
    """Booking requests with missing details ask a safe clarification before LLM tool use."""
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
    assert "full name" in result["response"].lower()
    assert "appointment date" in result["response"].lower()


@pytest.mark.anyio
async def test_process_chat_voice_mode(mock_redis, mock_llm_plain_response):
    """Voice booking mode can answer deterministically when details are missing."""
    with patch("agents.booking_agent.llm_router") as mock_router:
        mock_router.call = AsyncMock(return_value=mock_llm_plain_response)
        result = await process_chat_message(
            user_id="test-user",
            message="Book appointment",
            redis_client=mock_redis,
            mode="voice",
        )
        mock_router.call.assert_not_called()
        assert "full name" in result["response"].lower()


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
