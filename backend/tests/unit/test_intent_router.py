"""
tests/unit/test_intent_router.py

Unit tests for the intent classification logic.
Verifies that patient messages are correctly routed to OPERATIONAL or INFORMATIONAL.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.intent_router import route_intent

@pytest.mark.asyncio
async def test_intent_router_operational_examples():
    """Verify that booking-related messages route to OPERATIONAL."""
    test_cases = [
        "I want to book an appointment with Dr. Nadia",
        "Can I reschedule my visit for tomorrow?",
        "Cancel my 3 PM slot please",
        "What is the wait time right now?",
        "Is the doctor available for a checkup?",
    ]
    
    for msg in test_cases:
        mock_resp = MagicMock()
        mock_resp.text = "OPERATIONAL"
        with patch("services.llm_router.llm_router.call", AsyncMock(return_value=mock_resp)):
            result = await route_intent(msg)
            assert result == "OPERATIONAL", f"Failed for: {msg}"

@pytest.mark.asyncio
async def test_intent_router_informational_examples():
    """Verify that policy/info-related messages route to INFORMATIONAL."""
    test_cases = [
        "What are your opening hours on Saturday?",
        "Do you accept insurance from Jubilee?",
        "What are the consultation fees?",
        "Where can I park my car?",
        "Tell me about Dr. Nadia's qualifications",
        "What should I bring for my first visit?",
    ]
    
    for msg in test_cases:
        mock_resp = MagicMock()
        mock_resp.text = "INFORMATIONAL"
        with patch("services.llm_router.llm_router.call", AsyncMock(return_value=mock_resp)):
            result = await route_intent(msg)
            assert result == "INFORMATIONAL", f"Failed for: {msg}"

@pytest.mark.asyncio
async def test_intent_router_handles_extra_text():
    """Verify that the router extracts the keyword even if LLM is wordy."""
    mock_resp = MagicMock()
    mock_resp.text = "This message is INFORMATIONAL because it asks about hours."
    
    with patch("services.llm_router.llm_router.call", AsyncMock(return_value=mock_resp)):
        result = await route_intent("What time do you close?")
        assert result == "INFORMATIONAL"

@pytest.mark.asyncio
async def test_intent_router_case_insensitivity():
    """Verify that 'informational' (lowercase) is handled correctly."""
    mock_resp = MagicMock()
    mock_resp.text = "informational"
    
    with patch("services.llm_router.llm_router.call", AsyncMock(return_value=mock_resp)):
        result = await route_intent("Tell me about policies")
        assert result == "INFORMATIONAL"

@pytest.mark.asyncio
async def test_intent_router_fallback_on_llm_failure():
    """If the LLM fails, we must default to OPERATIONAL (Booking Agent)."""
    with patch("services.llm_router.llm_router.call", AsyncMock(side_effect=Exception("Timeout"))):
        result = await route_intent("Any message")
        assert result == "OPERATIONAL"

@pytest.mark.asyncio
async def test_intent_router_fallback_on_garbage_output():
    """If the LLM returns neither keyword, default to OPERATIONAL."""
    mock_resp = MagicMock()
    mock_resp.text = "I am not sure what this is."
    
    with patch("services.llm_router.llm_router.call", AsyncMock(return_value=mock_resp)):
        result = await route_intent("Random text")
        assert result == "OPERATIONAL"

@pytest.mark.asyncio
async def test_intent_router_uses_extraction_task():
    """Verify that the router uses the 'extraction' task type for low latency."""
    mock_resp = MagicMock()
    mock_resp.text = "OPERATIONAL"
    
    with patch("services.llm_router.llm_router.call", AsyncMock(return_value=mock_resp)) as mock_call:
        await route_intent("Book me now")
        # Check call arguments
        assert mock_call.call_args.kwargs["task_type"] == "extraction"
        assert "OPERATIONAL or INFORMATIONAL" in mock_call.call_args.kwargs["system"]
