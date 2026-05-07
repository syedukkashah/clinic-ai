"""
tests/integration/test_voice_rag_flow.py

Integration test for the Voice + RAG pipeline.
Verifies that voice requests for informational content correctly route to RAG
and apply the voice-specific sentence constraints.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.voice_service import handle_voice_request
from agents.orchestrator import orchestrator
from agents.booking_agent import AgentResponse

@pytest.mark.asyncio
async def test_voice_request_routes_to_rag_with_constraint():
    """
    E2E flow: 
    1. STT transcribes "What are the clinic hours?"
    2. Orchestrator identifies INFORMATIONAL intent
    3. RAG Service is queried with mode="voice"
    4. RAG LLM call includes "Respond in maximum 2 sentences."
    5. TTS synthesizes the response
    """
    session_id = "integration-voice-rag-test"
    audio_data = b"dummy_audio"
    
    # 1. Mock STT to return an informational question
    mock_stt_result = {"transcript": "What are the clinic hours?", "lang": "en"}
    
    # 2. Mock Intent Router to return INFORMATIONAL
    # We patch the router call inside orchestrator.handle_booking
    
    # 3. Mock RAG query results
    mock_rag_docs = {
        "documents": [["The clinic is open from 9 AM to 9 PM, Monday through Saturday."]],
        "metadatas": [[{"source": "clinic_overview"}]],
    }
    
    # 4. Mock LLM response
    mock_llm_resp = MagicMock()
    mock_llm_resp.text = "The clinic is open from 9 AM to 9 PM, Monday to Saturday. We are closed on Sundays."
    
    # 5. Mock TTS
    
    # Setup RAG singleton for test
    from services.rag_service import rag_service
    mock_collection = MagicMock()
    mock_collection.query.return_value = mock_rag_docs
    
    with patch("services.stt_service.transcribe_file", AsyncMock(return_value=mock_stt_result)), \
         patch("agents.orchestrator.route_intent", AsyncMock(return_value="INFORMATIONAL")), \
         patch.object(rag_service, "_init_client", MagicMock()), \
         patch.object(rag_service, "_collection", mock_collection), \
         patch("services.llm_router.llm_router.call", AsyncMock(return_value=mock_llm_resp)) as mock_llm_call, \
         patch("services.tts_service.synthesize", AsyncMock()) as mock_tts_call:
        
        # Execute the full voice request handler
        result = await handle_voice_request(audio_data, session_id)
        
        # --- Verifications ---
        
        # Verify text response
        assert result["text_response"] == mock_llm_resp.text
        assert result["transcript"] == "What are the clinic hours?"
        assert result["appointment"] is None
        
        # Verify RAG LLM prompt had the voice constraint
        rag_prompt = mock_llm_call.call_args.kwargs['messages'][0]['content']
        # Debug: print(f"DEBUG RAG PROMPT: {rag_prompt}")
        
        assert "Respond in maximum 2 sentences." in rag_prompt
        assert "clinic hours" in rag_prompt.lower()
        
        # Verify TTS was called with the final message
        mock_tts_call.assert_called_once()
        assert mock_tts_call.call_args[0][0] == mock_llm_resp.text

@pytest.mark.asyncio
async def test_voice_request_routes_to_booking_agent_for_operational():
    """
    Verifies that operational queries still route to the BookingAgent.
    """
    session_id = "integration-voice-op-test"
    audio_data = b"dummy_audio"
    
    mock_stt_result = {"transcript": "I want to book an appointment.", "lang": "en"}
    
    mock_agent_resp = AgentResponse(
        message="Sure, I can help with that. What department?",
        appointment_data={"status": "pending"}
    )
    
    with patch("services.stt_service.transcribe_file", AsyncMock(return_value=mock_stt_result)), \
         patch("services.intent_router.route_intent", AsyncMock(return_value="OPERATIONAL")), \
         patch("agents.orchestrator.booking_agent.run", AsyncMock(return_value=mock_agent_resp)), \
         patch("services.tts_service.synthesize", AsyncMock()):
        
        result = await handle_voice_request(audio_data, session_id)
        
        assert result["text_response"] == "Sure, I can help with that. What department?"
        assert result["appointment"] == {"status": "pending"}
