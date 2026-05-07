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

    result = await svc.query("What should I do before appointment?")
    assert "0800-MEDIFLOW" in result


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
