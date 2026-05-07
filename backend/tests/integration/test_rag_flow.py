
"""
RAG Integration Tests
=====================
Tests the full flow: Intent Router → Orchestrator → RAG Service.
All external calls are mocked.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_rag_full_integration_flow():
    """Test the complete RAG flow from end to end."""
    from agents.orchestrator import orchestrator
    from services.rag_service import rag_service

    test_question = "What are your opening hours?"
    test_answer = "Our clinic is open from 9:00 AM to 5:00 PM, Monday through Saturday."

    with patch("agents.orchestrator.route_intent", AsyncMock(return_value="INFORMATIONAL")):
        with patch.object(rag_service, "query", AsyncMock(return_value=test_answer)):
            with patch("agents.booking_agent.llm_router.call", AsyncMock()):
                result = await orchestrator.handle_booking(
                    test_question,
                    "test_integration_session_rag",
                    "en",
                    "text"
                )

    assert result.message == test_answer
    assert result.appointment_data is None


@pytest.mark.asyncio
async def test_rag_voice_mode_integration():
    """Test RAG flow in voice mode."""
    from agents.orchestrator import orchestrator
    from services.rag_service import rag_service

    test_question = "What should I bring to my appointment?"
    test_answer = "Please bring your ID, insurance card, and any previous medical records."

    with patch("agents.orchestrator.route_intent", AsyncMock(return_value="INFORMATIONAL")):
        with patch.object(rag_service, "query", AsyncMock(return_value=test_answer)):
            with patch("agents.booking_agent.llm_router.call", AsyncMock()):
                result = await orchestrator.handle_booking(
                    test_question,
                    "test_voice_session_rag",
                    "en",
                    "voice"
                )

    assert result.message == test_answer
    assert result.appointment_data is None


@pytest.mark.asyncio
async def test_rag_urdu_integration():
    """Test RAG flow with Urdu language."""
    from agents.orchestrator import orchestrator
    from services.rag_service import rag_service

    test_question = "آپ کے کھلنے کے اوقات کیا ہیں؟"
    test_answer = "ہمارا کلینک پیر سے ہفتہ تک صبح 9 بجے سے شام 5 بجے تک کھلتا ہے۔"

    with patch("agents.orchestrator.route_intent", AsyncMock(return_value="INFORMATIONAL")):
        with patch.object(rag_service, "query", AsyncMock(return_value=test_answer)):
            with patch("agents.booking_agent.llm_router.call", AsyncMock()):
                result = await orchestrator.handle_booking(
                    test_question,
                    "test_urdu_session_rag",
                    "ur",
                    "text"
                )

    assert result.message == test_answer
    assert result.appointment_data is None
