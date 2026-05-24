from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.intent_router import route_intent


def _resp(text: str):
    return MagicMock(text=text)


class TestIntentRouterMocked:
    @pytest.mark.asyncio
    async def test_operational_intent_book(self):
        with patch("services.intent_router.llm_router.call", AsyncMock(return_value=_resp("OPERATIONAL"))):
            assert await route_intent("Book me an appointment for tomorrow") == "OPERATIONAL"

    @pytest.mark.asyncio
    async def test_operational_intent_cancel(self):
        with patch("services.intent_router.llm_router.call", AsyncMock(return_value=_resp("OPERATIONAL"))):
            assert await route_intent("Cancel my appointment") == "OPERATIONAL"

    @pytest.mark.asyncio
    async def test_informational_intent_hours(self):
        with patch("services.intent_router.llm_router.call", AsyncMock(return_value=_resp("INFORMATIONAL"))):
            assert await route_intent("What are your clinic hours?") == "INFORMATIONAL"

    @pytest.mark.asyncio
    async def test_informational_intent_doctor(self):
        with patch("services.intent_router.llm_router.call", AsyncMock(return_value=_resp("INFORMATIONAL"))):
            assert await route_intent("Tell me about Dr. Ahmed Raza") == "INFORMATIONAL"

    @pytest.mark.asyncio
    async def test_both_intent(self):
        with patch("services.intent_router.llm_router.call", AsyncMock(return_value=_resp("BOTH"))):
            assert await route_intent("Book cardiology and what should I bring?") == "BOTH"

    @pytest.mark.asyncio
    async def test_garbage_llm_response_falls_back(self):
        with patch("services.intent_router.llm_router.call", AsyncMock(return_value=_resp("I think this is operational"))):
            assert await route_intent("random message") == "OPERATIONAL"

    @pytest.mark.asyncio
    async def test_empty_llm_response_falls_back(self):
        with patch("services.intent_router.llm_router.call", AsyncMock(return_value=_resp(""))):
            assert await route_intent("random message") == "OPERATIONAL"

    @pytest.mark.asyncio
    async def test_exception_in_llm_falls_back(self):
        with patch("services.intent_router.llm_router.call", AsyncMock(side_effect=Exception("LLM timeout"))):
            assert await route_intent("random message") == "OPERATIONAL"

    @pytest.mark.asyncio
    async def test_empty_message_returns_operational(self):
        with patch("services.intent_router.llm_router.call", AsyncMock()) as mock_call:
            assert await route_intent("") == "OPERATIONAL"
            mock_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_whitespace_message_returns_operational(self):
        with patch("services.intent_router.llm_router.call", AsyncMock()) as mock_call:
            assert await route_intent("   \n  ") == "OPERATIONAL"
            mock_call.assert_not_called()


class TestIntentRouterKeywords:
    @pytest.mark.asyncio
    async def test_reschedule_is_operational(self):
        async def classify(**kwargs):
            assert "reschedule" in kwargs["messages"][0]["content"].lower()
            return _resp("OPERATIONAL")

        with patch("services.intent_router.llm_router.call", AsyncMock(side_effect=classify)):
            assert await route_intent("I need to reschedule my appointment") == "OPERATIONAL"

    @pytest.mark.asyncio
    async def test_which_doctor_symptom_is_informational(self):
        with patch("services.intent_router.llm_router.call", AsyncMock()) as mock_call:
            assert await route_intent("I have back pain, which doctor should I see?") == "INFORMATIONAL"
            mock_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_is_doctor_available_is_operational(self):
        async def classify(**kwargs):
            assert "available" in kwargs["messages"][0]["content"].lower()
            return _resp("OPERATIONAL")

        with patch("services.intent_router.llm_router.call", AsyncMock(side_effect=classify)):
            assert await route_intent("Is Dr. Tariq Butt available on Friday?") == "OPERATIONAL"

    @pytest.mark.asyncio
    async def test_mixed_book_and_bring_is_both(self):
        with patch("services.intent_router.llm_router.call", AsyncMock()) as mock_call:
            result = await route_intent("I want to book Dr. Nadia Hussain and also need to know what to bring")
            assert result == "BOTH"
            mock_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_fee_only_is_informational(self):
        with patch("services.intent_router.llm_router.call", AsyncMock()) as mock_call:
            assert await route_intent("How much does a cardiology appointment cost?") == "INFORMATIONAL"
            mock_call.assert_not_called()
