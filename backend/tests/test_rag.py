"""
tests/test_rag.py

Unit tests for the RAG pipeline: intent_router and rag_service.
All LLM and ChromaDB interactions are mocked — no API keys or vector store needed.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# 1. test_route_intent_informational
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_route_intent_informational():
    """LLM returns INFORMATIONAL → route_intent should return INFORMATIONAL."""
    mock_resp = MagicMock()
    mock_resp.text = "INFORMATIONAL"
    with patch("services.intent_router.llm_router") as mock_router:
        mock_router.call = AsyncMock(return_value=mock_resp)
        from services.intent_router import route_intent
        result = await route_intent("What are your opening hours?")
        assert result == "INFORMATIONAL"


# ---------------------------------------------------------------------------
# 2. test_route_intent_operational
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_route_intent_operational():
    """LLM returns OPERATIONAL → route_intent should return OPERATIONAL."""
    mock_resp = MagicMock()
    mock_resp.text = "OPERATIONAL"
    with patch("services.intent_router.llm_router") as mock_router:
        mock_router.call = AsyncMock(return_value=mock_resp)
        from services.intent_router import route_intent
        result = await route_intent("Book me an appointment for tomorrow")
        assert result == "OPERATIONAL"


# ---------------------------------------------------------------------------
# 3. test_route_intent_fallback_on_failure
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_route_intent_fallback_on_failure():
    """LLM raises an exception → route_intent should default to OPERATIONAL."""
    with patch("services.intent_router.llm_router") as mock_router:
        mock_router.call = AsyncMock(side_effect=Exception("LLM down"))
        from services.intent_router import route_intent
        result = await route_intent("some message")
        assert result == "OPERATIONAL"


@pytest.mark.asyncio
async def test_route_intent_common_faq_uses_keywords_without_llm():
    """Common clinic FAQ phrases should route to RAG even if the classifier is unavailable."""
    with patch("services.intent_router.llm_router") as mock_router:
        mock_router.call = AsyncMock(side_effect=Exception("LLM down"))
        from services.intent_router import route_intent
        result = await route_intent("What are your clinic timings and parking policy?")
        assert result == "INFORMATIONAL"
        mock_router.call.assert_not_called()


# ---------------------------------------------------------------------------
# 4. test_rag_query_returns_grounded_answer
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rag_query_returns_grounded_answer():
    """RAG query with valid chunks returns the LLM-generated answer."""
    from services.rag_service import RAGService

    svc = RAGService.__new__(RAGService)
    svc._client = MagicMock()
    svc._embed_fn = MagicMock()

    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "documents": [["Fasting for 12 hours is required before a cardiology visit."]],
        "metadatas": [[{"source": "preparation_instructions"}]],
    }
    svc._collection = mock_collection

    mock_llm_resp = MagicMock()
    mock_llm_resp.text = "Please fast for 12 hours before your cardiology appointment."

    mock_router = MagicMock()
    mock_router.call = AsyncMock(return_value=mock_llm_resp)
    with patch("services.llm_router.llm_router", mock_router):
        result = await svc.query("What should I do before a cardiology visit?")

    assert "fast" in result.lower() or "12 hours" in result.lower()
    mock_collection.query.assert_called_once()


# ---------------------------------------------------------------------------
# 5. test_rag_query_empty_results_returns_fallback
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rag_query_empty_results_returns_fallback():
    """RAG query with no matching chunks returns the fallback message."""
    from services.rag_service import RAGService

    svc = RAGService.__new__(RAGService)
    svc._client = MagicMock()
    svc._embed_fn = MagicMock()

    mock_collection = MagicMock()
    mock_collection.query.return_value = {"documents": [[]], "metadatas": [[]]}
    svc._collection = mock_collection

    result = await svc.query("something completely obscure")
    assert "0800-MEDIFLOW" in result


# ---------------------------------------------------------------------------
# 6. test_rag_query_urdu_uses_urdu_task
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rag_query_urdu_uses_urdu_task():
    """When language='ur', RAG should pass task_type='urdu' to llm_router."""
    from services.rag_service import RAGService

    svc = RAGService.__new__(RAGService)
    svc._client = MagicMock()
    svc._embed_fn = MagicMock()

    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "documents": [["Dr. Nadia is an interventional cardiologist."]],
        "metadatas": [[{"source": "doctor_profiles"}]],
    }
    svc._collection = mock_collection

    mock_llm_resp = MagicMock()
    mock_llm_resp.text = "ڈاکٹر نادیہ ایک انٹرونشنل کارڈیالوجسٹ ہیں۔"

    mock_router = MagicMock()
    mock_router.call = AsyncMock(return_value=mock_llm_resp)
    with patch("services.llm_router.llm_router", mock_router):
        await svc.query("Dr. Nadia ki specialization kya hai?", language="ur")
        # Verify task_type="urdu" was passed
        call_kwargs = mock_router.call.call_args
        assert call_kwargs.kwargs.get("task_type") == "urdu"


# ---------------------------------------------------------------------------
# 7. test_rag_ingest_creates_chunks
# ---------------------------------------------------------------------------
def test_rag_ingest_creates_chunks(tmp_path):
    """Ingest reads .txt files, chunks them, and calls collection.add()."""
    from services.rag_service import RAGService, CHUNK_SIZE

    # Create temp doc files
    docs_dir = tmp_path / "clinic_docs"
    docs_dir.mkdir()
    (docs_dir / "test_doc.txt").write_text("A" * (CHUNK_SIZE + 100), encoding="utf-8")

    svc = RAGService.__new__(RAGService)
    svc._client = MagicMock()
    svc._embed_fn = MagicMock()

    mock_collection = MagicMock()
    svc._collection = mock_collection
    # Mock create_collection to return the same mock
    svc._client.create_collection.return_value = mock_collection
    svc._client.delete_collection = MagicMock()

    # Patch DOCS_DIR to use tmp_path
    with patch("services.rag_service.DOCS_DIR", docs_dir):
        n = svc.ingest_documents()

    assert n > 0
    mock_collection.add.assert_called()


# ---------------------------------------------------------------------------
# 8. test_ensure_collection_populated_skips_if_not_empty
# ---------------------------------------------------------------------------
def test_ensure_collection_populated_skips_if_not_empty():
    """If collection already has chunks, ensure_collection_populated does NOT re-ingest."""
    from services.rag_service import RAGService

    svc = RAGService.__new__(RAGService)
    svc._client = MagicMock()
    svc._embed_fn = MagicMock()

    mock_collection = MagicMock()
    mock_collection.count.return_value = 150  # already populated
    svc._collection = mock_collection

    with patch.object(svc, "ingest_documents") as mock_ingest:
        svc.ensure_collection_populated()
        mock_ingest.assert_not_called()


# ---------------------------------------------------------------------------
# 9. test_orchestrator_routes_informational_to_rag
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_orchestrator_routes_informational_to_rag():
    """Orchestrator should route INFORMATIONAL queries to RAG service."""
    from agents.orchestrator import orchestrator
    from services.rag_service import rag_service

    test_answer = "Clinic is open from 9 AM to 5 PM."
    with patch("agents.orchestrator.route_intent", AsyncMock(return_value="INFORMATIONAL")):
        with patch.object(rag_service, "query", AsyncMock(return_value=test_answer)):
            with patch("agents.booking_agent.llm_router.call", AsyncMock()):
                result = await orchestrator.handle_booking(
                    "What are your opening hours?", 
                    "test_session_rag", 
                    "en", 
                    "text"
                )
    
    assert result.message == test_answer
    assert result.appointment_data is None


@pytest.mark.asyncio
async def test_orchestrator_both_intent_combines_rag_and_booking():
    """Mixed intent should return RAG context and booking output in one response."""
    from agents.booking_agent import AgentResponse
    from agents.orchestrator import orchestrator
    from services.rag_service import rag_service

    booking_response = AgentResponse(
        message="Here are cardiology slots.",
        appointment_data=None,
        suggested_slots=[{"doctor_name": "Dr. Tariq Butt"}],
    )

    with patch("agents.orchestrator.route_intent", AsyncMock(return_value="BOTH")), \
         patch.object(rag_service, "query", AsyncMock(return_value="Dr. Tariq Butt charges PKR 2500.")), \
         patch("agents.orchestrator.booking_agent.run", AsyncMock(return_value=booking_response)):
        result = await orchestrator.handle_booking(
            "Book me Dr. Tariq Butt and also tell me his fee",
            "test_both_intent",
            "en",
            "text",
        )

    assert "PKR 2500" in result.message
    assert "Here are cardiology slots" in result.message
    assert result.suggested_slots == [{"doctor_name": "Dr. Tariq Butt"}]


@pytest.mark.asyncio
async def test_orchestrator_appends_prep_info_after_confirmed_booking():
    """Confirmed booking responses should include automatic prep guidance."""
    from agents.booking_agent import AgentResponse
    from agents.orchestrator import orchestrator
    from services.rag_service import rag_service

    booking_response = AgentResponse(
        message="Appointment confirmed with Dr. Tariq Butt.",
        appointment_data={"specialty": "cardiology", "status": "confirmed"},
    )

    with patch("agents.orchestrator.route_intent", AsyncMock(return_value="OPERATIONAL")), \
         patch.object(rag_service, "query", AsyncMock(return_value="Bring ECG reports and a medication list.")), \
         patch("agents.orchestrator.booking_agent.run", AsyncMock(return_value=booking_response)):
        result = await orchestrator.handle_booking(
            "Book me a cardiology appointment",
            "test_prep_enrichment",
            "en",
            "text",
        )

    assert "Appointment confirmed" in result.message
    assert "Preparation Reminder" in result.message
    assert "ECG reports" in result.message


@pytest.mark.asyncio
async def test_orchestrator_active_booking_can_route_faq_to_rag():
    """A stale booking state must not trap FAQ queries in the booking prompt loop."""
    from agents.orchestrator import orchestrator
    from services.rag_service import rag_service

    class FakeRedis:
        def __init__(self):
            self.store = {}

        async def get(self, key):
            return self.store.get(key)

        async def setex(self, key, ttl, value):
            self.store[key] = value

        async def delete(self, key):
            self.store.pop(key, None)

    redis = FakeRedis()
    await redis.setex(
        "session:test_active_faq:booking",
        1800,
        '{"active": true, "specialty": "general"}',
    )

    test_answer = "Clinic hours are Monday to Saturday 9am to 8pm."
    with patch("agents.orchestrator.route_intent", AsyncMock(return_value="INFORMATIONAL")):
        with patch.object(rag_service, "query", AsyncMock(return_value=test_answer)) as mock_rag:
            result = await orchestrator.handle_booking(
                "Clinic hours",
                "test_active_faq",
                "en",
                "text",
                redis=redis,
            )

    assert result.message == test_answer
    assert result.intent == "informational_query"
    mock_rag.assert_awaited_once()
    assert await redis.get("session:test_active_faq:booking") is None


@pytest.mark.asyncio
async def test_orchestrator_reschedule_can_be_paused_then_faq_routes_to_rag():
    """Patients can leave a reschedule flow and ask a FAQ without the booking prompt repeating."""
    from agents.orchestrator import orchestrator
    from services.rag_service import rag_service

    class FakeRedis:
        def __init__(self):
            self.store = {}

        async def get(self, key):
            return self.store.get(key)

        async def setex(self, key, ttl, value):
            self.store[key] = value

        async def delete(self, key):
            self.store.pop(key, None)

    redis = FakeRedis()
    session_id = "test_reschedule_escape"
    faq_answer = "Clinic hours are Monday to Friday, 9:00 AM to 5:00 PM."

    with patch("agents.orchestrator.route_intent", AsyncMock(return_value="INFORMATIONAL")), patch.object(
        rag_service,
        "query",
        AsyncMock(return_value=faq_answer),
    ) as mock_rag:
        first = await orchestrator.handle_booking(
            "hello, I need to reschedule an appointment",
            session_id,
            "en",
            "text",
            redis=redis,
        )
        second = await orchestrator.handle_booking(
            "doctor sara, ID: apt-123. Date: 2026-05-18 at 10:00.",
            session_id,
            "en",
            "text",
            redis=redis,
        )
        paused = await orchestrator.handle_booking("nvm", session_id, "en", "text", redis=redis)
        faq = await orchestrator.handle_booking("Clinic hours", session_id, "en", "text", redis=redis)

    assert "appointment id" in first.message.lower()
    assert "new appointment date" in second.message.lower()
    assert "reason for visit" not in second.message.lower()
    assert "paused" in paused.message.lower()
    assert faq.message == faq_answer
    assert "which doctor or department" not in faq.message.lower()
    mock_rag.assert_awaited_once()


@pytest.mark.asyncio
async def test_orchestrator_active_booking_operational_turn_skips_llm_router():
    """Active booking turns should stay operational without paying for intent LLM calls."""
    from agents.orchestrator import orchestrator

    class FakeRedis:
        def __init__(self):
            self.store = {}

        async def get(self, key):
            return self.store.get(key)

        async def setex(self, key, ttl, value):
            self.store[key] = value

        async def delete(self, key):
            self.store.pop(key, None)

    redis = FakeRedis()
    await redis.setex(
        "session:test_active_booking_cost:booking",
        1800,
        '{"active": true, "doctor_id": 2, "doctor_name": "Sara Malik", "date": "2026-05-18"}',
    )

    with patch("agents.orchestrator.route_intent", AsyncMock(return_value="INFORMATIONAL")) as mock_route, patch(
        "agents.orchestrator.BookingAgent"
    ) as mock_agent_cls:
        mock_agent = mock_agent_cls.return_value
        mock_agent.run = AsyncMock(
            return_value=type(
                "Response",
                (),
                {"message": "Please share appointment time.", "appointment_data": None, "intent": "booking_intent"},
            )()
        )

        result = await orchestrator.handle_booking(
            "my contact number is 03352034811",
            "test_active_booking_cost",
            "en",
            "text",
            redis=redis,
        )

    mock_route.assert_not_called()
    mock_agent.run.assert_awaited_once()
    assert result.message == "Please share appointment time."


@pytest.mark.asyncio
async def test_orchestrator_abort_phrase_with_punctuation_clears_booking_state():
    """Abort detection should handle common punctuation variants like 'nvm!'."""
    from agents.orchestrator import orchestrator

    class FakeRedis:
        def __init__(self):
            self.store = {}

        async def get(self, key):
            return self.store.get(key)

        async def setex(self, key, ttl, value):
            self.store[key] = value

        async def delete(self, key):
            self.store.pop(key, None)

    redis = FakeRedis()
    await redis.setex(
        "session:test_abort_punctuation:booking",
        1800,
        '{"active": true, "specialty": "general"}',
    )

    with patch("agents.orchestrator.route_intent", AsyncMock()) as mock_route:
        result = await orchestrator.handle_booking(
            "nvm!",
            "test_abort_punctuation",
            "en",
            "text",
            redis=redis,
        )

    assert "paused" in result.message.lower()
    assert await redis.get("session:test_abort_punctuation:booking") is None
    mock_route.assert_not_called()


# ---------------------------------------------------------------------------
# 10. test_rag_query_chroma_failure_returns_fallback
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rag_query_chroma_failure_returns_fallback():
    """RAG query with ChromaDB failure returns fallback message."""
    from services.rag_service import RAGService

    svc = RAGService.__new__(RAGService)
    svc._client = MagicMock()
    svc._embed_fn = MagicMock()

    mock_collection = MagicMock()
    mock_collection.query.side_effect = Exception("ChromaDB is down")
    svc._collection = mock_collection

    with patch.object(svc, "_load_document_chunks", return_value=[]):
        result = await svc.query("What should I do before appointment?")
    assert "0800-MEDIFLOW" in result


@pytest.mark.asyncio
async def test_rag_chroma_failure_uses_lexical_docs_and_extractive_answer():
    """If Chroma is down, RAG should still answer from local clinic docs."""
    from services.rag_service import RAGService

    svc = RAGService.__new__(RAGService)
    svc._client = MagicMock()
    svc._embed_fn = MagicMock()

    mock_collection = MagicMock()
    mock_collection.query.side_effect = Exception("ChromaDB is down")
    svc._collection = mock_collection

    mock_router = MagicMock()
    mock_router.call = AsyncMock(side_effect=Exception("LLM down"))
    with patch("services.llm_router.llm_router", mock_router):
        result = await svc.query("What documents should I bring to my appointment?")

    assert "CNIC" in result or "Insurance" in result or "medical reports" in result
    assert "0800-MEDIFLOW" not in result


# ---------------------------------------------------------------------------
# 11. test_rag_query_llm_failure_returns_fallback
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rag_query_llm_failure_returns_fallback():
    """RAG query with LLM failure returns fallback message."""
    from services.rag_service import RAGService

    svc = RAGService.__new__(RAGService)
    svc._client = MagicMock()
    svc._embed_fn = MagicMock()

    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "documents": [["Fasting is required."]],
        "metadatas": [[{"source": "prep"}]],
    }
    svc._collection = mock_collection

    mock_router = MagicMock()
    mock_router.call = AsyncMock(side_effect=Exception("LLM down"))
    with patch("services.llm_router.llm_router", mock_router):
        result = await svc.query("What should I do?")

    assert "0800-MEDIFLOW" in result


@pytest.mark.asyncio
async def test_rag_llm_failure_returns_grounded_extractive_answer():
    """If retrieval works but LLM fails, RAG should still answer from retrieved lines."""
    from services.rag_service import RAGService

    svc = RAGService.__new__(RAGService)
    svc._client = MagicMock()
    svc._embed_fn = MagicMock()
    svc._doc_chunks = []

    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "documents": [[
            "REQUIRED DOCUMENTS TO BRING:\n- Original CNIC for adults.\n- Insurance card if applicable.\n- Previous medical reports if available."
        ]],
        "metadatas": [[{"source": "visiting_guidelines"}]],
    }
    svc._collection = mock_collection

    mock_router = MagicMock()
    mock_router.call = AsyncMock(side_effect=Exception("LLM down"))
    with patch("services.llm_router.llm_router", mock_router):
        result = await svc.query("What documents should I bring?")

    assert "CNIC" in result
    assert "0800-MEDIFLOW" not in result


@pytest.mark.asyncio
async def test_rag_unhelpful_llm_answer_falls_back_to_context():
    """If LLM refuses despite relevant context, use the retrieved context directly."""
    from services.rag_service import RAGService

    svc = RAGService.__new__(RAGService)
    svc._client = MagicMock()
    svc._embed_fn = MagicMock()
    svc._doc_chunks = []

    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "documents": [["Opening hours: Monday to Saturday 9am to 8pm\nSunday: 9am to 2pm"]],
        "metadatas": [[{"source": "clinic_overview"}]],
    }
    svc._collection = mock_collection

    mock_llm_resp = MagicMock()
    mock_llm_resp.text = "I don't have that specific information. Please call 0800-MEDIFLOW."
    mock_router = MagicMock()
    mock_router.call = AsyncMock(return_value=mock_llm_resp)
    with patch("services.llm_router.llm_router", mock_router):
        result = await svc.query("What are your opening hours?")

    assert "Monday to Saturday" in result
    assert "0800-MEDIFLOW" not in result


@pytest.mark.asyncio
async def test_orchestrator_rag_exception_returns_safe_response():
    """A RAG exception should not break the chat or voice pipeline."""
    from agents.orchestrator import orchestrator
    from services.rag_service import rag_service

    with patch("agents.orchestrator.route_intent", AsyncMock(return_value="INFORMATIONAL")):
        with patch.object(rag_service, "query", AsyncMock(side_effect=RuntimeError("RAG crashed"))):
            result = await orchestrator.handle_booking(
                "What are your opening hours?",
                "test_rag_exception_session",
                "en",
                "text",
            )

    assert "0800-MEDIFLOW" in result.message
    assert result.intent == "informational_query"


# ---------------------------------------------------------------------------
# 12. test_intent_router_case_insensitive
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_intent_router_case_insensitive():
    """Intent router should work with lowercase/uppercase responses."""
    from services.intent_router import route_intent

    mock_resp = MagicMock()
    mock_resp.text = "informational"
    with patch("services.intent_router.llm_router") as mock_router:
        mock_router.call = AsyncMock(return_value=mock_resp)
        result = await route_intent("Clinic hours?")
        assert result == "INFORMATIONAL"

    mock_resp = MagicMock()
    mock_resp.text = "Operational"
    with patch("services.intent_router.llm_router") as mock_router:
        mock_router.call = AsyncMock(return_value=mock_resp)
        result = await route_intent("Book appointment")
        assert result == "OPERATIONAL"
