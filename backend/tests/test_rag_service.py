from __future__ import annotations

import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.rag_service import COLLECTION_NAME, RAGService


ARABIC_RE = re.compile(r"[\u0600-\u06FF]")


def _service_with_chunks(source: str, text: str) -> RAGService:
    svc = RAGService.__new__(RAGService)
    svc._client = MagicMock()
    svc._embed_fn = MagicMock()
    svc._doc_chunks = []
    collection = MagicMock()
    collection.query.return_value = {
        "documents": [[text]],
        "metadatas": [[{"source": source}]],
    }
    svc._collection = collection
    return svc


async def _query_with_answer(source: str, chunk: str, question: str, answer: str, **kwargs) -> str:
    svc = _service_with_chunks(source, chunk)
    resp = MagicMock(text=answer)
    with patch("services.llm_router.llm_router.call", AsyncMock(return_value=resp)):
        return await svc.query(question, **kwargs)


class TestRAGQuery:
    @pytest.mark.asyncio
    async def test_english_faq_query(self):
        response = await _query_with_answer(
            "clinic_overview",
            "Clinic hours are 9 AM to 8 PM Monday to Saturday.",
            "What are your clinic hours?",
            "MediFlow is open from 9 AM to 8 PM Monday to Saturday.",
        )
        assert isinstance(response, str)
        assert len(response) > 30
        assert "9" in response or "8" in response
        assert not ARABIC_RE.search(response)

    @pytest.mark.asyncio
    async def test_urdu_faq_query(self):
        response = await _query_with_answer(
            "clinic_overview",
            "Clinic hours are 9 AM to 8 PM.",
            "کلینک کے اوقات کیا ہیں؟",
            "میڈی فلو صبح 9 بجے سے رات 8 بجے تک کھلا رہتا ہے۔",
            language="ur",
        )
        assert response
        assert ARABIC_RE.search(response)
        assert not response.startswith("I")

    @pytest.mark.asyncio
    async def test_doctor_profile_query(self):
        response = await _query_with_answer(
            "doctor_profiles",
            "Dr. Nadia Hussain is a cardiologist. Fee PKR 3000.",
            "Tell me about Dr. Nadia Hussain",
            "Dr. Nadia Hussain is an experienced cardiologist. Her fee is PKR 3000.",
        )
        assert any(token in response for token in ("Nadia", "Hussain", "cardiolog"))
        assert any(token in response for token in ("PKR", "fee", "2500", "3000"))
        assert "I don't have information" not in response

    @pytest.mark.asyncio
    async def test_symptom_to_specialty_query(self):
        response = await _query_with_answer(
            "symptom_specialty_guide",
            "Chest pain and palpitations are Cardiology. Dr. Tariq Butt and Dr. Nadia Hussain are options.",
            "I have chest pain and palpitations, which doctor should I see?",
            "You should see Cardiology, and Tariq Butt or Nadia Hussain can help with available slots.",
        )
        assert "cardiol" in response.lower()
        assert "Tariq" in response or "Nadia" in response
        assert response.endswith("?") or "slot" in response.lower() or "available" in response.lower()

    @pytest.mark.asyncio
    async def test_preparation_instructions_query(self):
        response = await _query_with_answer(
            "preparation_instructions",
            "Cardiology preparation: fast 4 hours, bring ECG reports and medication list.",
            "preparation instructions for cardiology appointment",
            "1. Fast for 4 hours.\n2. Bring ECG reports.\n3. Bring your medication list.",
        )
        assert any(term.lower() in response.lower() for term in ("fast", "ecg", "medication", "bring", "report", "4 hour"))
        assert "\n" in response or "1." in response

    @pytest.mark.asyncio
    async def test_pediatrics_preparation_urdu(self):
        response = await _query_with_answer(
            "preparation_instructions",
            "Bring the child's vaccination record and allergy list.",
            "بچے کی اپائنٹمنٹ سے پہلے کیا کرنا چاہیے؟",
            "بچے کا ویکسینیشن کارڈ، الرجی کی فہرست، اور پچھلی رپورٹس ساتھ لائیں۔",
            language="ur",
        )
        assert ARABIC_RE.search(response)
        assert any(term in response for term in ("کارڈ", "رپورٹ", "فہرست", "ساتھ"))

    @pytest.mark.asyncio
    async def test_emergency_query_surfaces_1122(self):
        response = await _query_with_answer(
            "emergency_guidance",
            "Severe chest pain with breathing difficulty is an emergency. Call 1122.",
            "I have severe chest pain right now and cannot breathe",
            "This is an emergency. Call 1122 immediately or go to the nearest emergency room.",
        )
        assert "1122" in response or "emergency" in response.lower()
        assert response.lower().strip() != "book cardiology"

    @pytest.mark.asyncio
    async def test_out_of_scope_query(self):
        svc = _service_with_chunks("clinic_overview", "")
        svc._collection.query.return_value = {"documents": [[]], "metadatas": [[]]}
        response = await svc.query("What is the weather forecast for Karachi tomorrow?")
        assert any(term in response for term in ("0800", "MEDIFLOW", "don't have"))
        assert "rain" not in response.lower()

    @pytest.mark.asyncio
    async def test_conversation_context_changes_answer(self):
        svc = _service_with_chunks(
            "preparation_instructions",
            "Dermatology prep: wash the skin gently, avoid creams and makeup, bring medication tubes.",
        )
        resp = MagicMock(text="Wash the affected skin gently, avoid creams or makeup, and bring any skin medication tubes.")
        context = [
            {"role": "user", "content": "I need a dermatology appointment"},
            {"role": "assistant", "content": "I can book you for dermatology."},
        ]
        with patch("services.llm_router.llm_router.call", AsyncMock(return_value=resp)) as mock_call:
            response = await svc.query("what should I bring?", conversation_context=context)
        prompt = mock_call.call_args.kwargs["messages"][0]["content"]
        assert "RECENT CONVERSATION" in prompt
        assert "dermatology" in prompt.lower()
        assert any(term in response.lower() for term in ("skin", "wash", "cream", "makeup", "moisturizer"))
        assert response.lower() != "bring cnic"

    @pytest.mark.asyncio
    async def test_context_does_not_contaminate_unrelated_query(self):
        svc = _service_with_chunks(
            "insurance_payments",
            "Payment methods include cash, bank transfer, JazzCash, EasyPaisa, Visa and Mastercard.",
        )
        resp = MagicMock(text="We accept cash, bank transfer, JazzCash, EasyPaisa, Visa and Mastercard.")
        context = [{"role": "user", "content": "I booked cardiology and need ECG prep."}]
        with patch("services.llm_router.llm_router.call", AsyncMock(return_value=resp)):
            response = await svc.query("What are your payment methods?", conversation_context=context)
        assert any(term in response for term in ("cash", "JazzCash", "Visa", "Mastercard"))
        assert "cardiology" not in response.lower()
        assert "ecg" not in response.lower()

    @pytest.mark.asyncio
    async def test_empty_message_handled_gracefully(self):
        svc = _service_with_chunks("clinic_overview", "")
        svc._collection.query.return_value = {"documents": [[]], "metadatas": [[]]}
        response = await svc.query("")
        assert isinstance(response, str)
        assert response

    @pytest.mark.asyncio
    async def test_very_long_query_handled(self):
        response = await _query_with_answer(
            "doctor_profiles",
            "Doctors at MediFlow include cardiology, pediatrics and dermatology specialists.",
            "I need information about " + ("doctors " * 200),
            "MediFlow has doctors across cardiology, pediatrics, dermatology, orthopedics and general medicine.",
        )
        assert response

    @pytest.mark.asyncio
    async def test_source_aware_response_style_doctor(self):
        svc = _service_with_chunks(
            "doctor_profiles",
            "Dr. Bilal Chaudhry is a pediatrician. Available Tuesday to Sunday. Fee PKR 1200.",
        )
        resp = MagicMock(
            text=(
                "Bilal Chaudhry is a pediatrician who treats childhood asthma and nutrition concerns. "
                "His fee is PKR 1200. He is available Tuesday to Sunday."
            )
        )
        with patch("services.llm_router.llm_router.call", AsyncMock(return_value=resp)) as mock_call:
            response = await svc.query("Tell me about Dr. Bilal Chaudhry")
        prompt = mock_call.call_args.kwargs["messages"][0]["content"]
        assert "Include their specialty" in prompt
        assert "PKR" in response
        assert "Tuesday" in response or "Sunday" in response
        assert response.count(".") >= 1

    @pytest.mark.asyncio
    async def test_source_aware_response_style_preparation(self):
        svc = _service_with_chunks(
            "preparation_instructions",
            "Orthopedics prep: bring X-ray, scans, reports and wear loose clothing for physical exam.",
        )
        resp = MagicMock(text="1. Bring X-ray or scan reports.\n2. Wear loose clothing for the physical exam.")
        with patch("services.llm_router.llm_router.call", AsyncMock(return_value=resp)) as mock_call:
            response = await svc.query("How should I prepare for my orthopedics appointment?")
        prompt = mock_call.call_args.kwargs["messages"][0]["content"]
        assert "short numbered list" in prompt
        assert "\n" in response or "1." in response or "-" in response
        assert any(term in response.lower() for term in ("x-ray", "scan", "report", "physical exam"))


class TestRAGIngestion:
    def test_all_documents_ingested(self):
        svc = RAGService.__new__(RAGService)
        svc._client = MagicMock()
        svc._embed_fn = MagicMock()
        svc._collection = MagicMock()
        collection = MagicMock()
        svc._client.create_collection.return_value = collection

        total = svc.ingest_documents()

        assert total > 100
        assert svc._client.create_collection.call_args.kwargs["name"] == COLLECTION_NAME
        collection.add.assert_called()

    def test_symptom_specialty_guide_ingested(self):
        svc = RAGService()
        results = svc._lexical_retrieve("knee pain orthopedics", limit=5)
        assert results
        assert any(item["source"] == "symptom_specialty_guide" for item in results)
        joined = " ".join(item["text"] for item in results).lower()
        assert "orthopedics" in joined or "hina javed" in joined

    def test_faqs_ingested(self):
        svc = RAGService()
        results = svc._lexical_retrieve("cancellation fee 2 hours", limit=5)
        assert results
        joined = " ".join(item["text"] for item in results)
        assert "200" in joined
