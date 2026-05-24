"""
Agent Orchestrator
==================

Single entry point for both chat and voice requests.
Routes INFORMATIONAL queries to RAG, OPERATIONAL queries to BookingAgent.
"""

from __future__ import annotations

import asyncio
import logging
import re

from agents.booking_agent import AgentResponse, booking_agent
from agents.booking_agent import BookingAgent
from services.intent_router import route_intent
from services.rag_service import rag_service
from services.redis_memory import clear_booking_state, get_booking_state, get_history
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from prometheus_client import Counter

logger = logging.getLogger(__name__)

PROM_AGENT_STEPS = Counter(
    "mediflow_agent_steps_total",
    "Agent tool calls",
    ["agent", "tool"]
)


_PREP_QUERIES = {
    "cardiology": "preparation instructions for cardiology appointment",
    "general": "preparation instructions for general medicine appointment",
    "general medicine": "preparation instructions for general medicine appointment",
    "general practice": "preparation instructions for general medicine appointment",
    "pediatrics": "preparation instructions for pediatric children appointment",
    "dermatology": "preparation instructions for dermatology skin appointment",
    "orthopedics": "preparation instructions for orthopedics bone joint appointment",
}

_PREP_SEPARATOR = {
    "en": "\n\n─────────────────────────\n📋 **Preparation Reminder**\n",
    "ur": "\n\n─────────────────────────\n📋 **تیاری کی یاددہانی**\n",
}


async def _append_prep_info(
    result: AgentResponse,
    language: str,
    rag_svc,
) -> AgentResponse:
    """
    Append specialty preparation instructions after a fresh confirmed booking.

    This is best-effort only: RAG timeout/failure must never affect booking.
    """
    try:
        appt = result.appointment_data
        if not appt:
            return result

        status = str(appt.get("status", "confirmed")).lower().strip()
        specialty = str(appt.get("specialty", "")).lower().strip()

        if status != "confirmed":
            return result
        if specialty not in _PREP_QUERIES:
            return result
        if _PREP_SEPARATOR["en"] in result.message or _PREP_SEPARATOR["ur"] in result.message:
            return result

        try:
            prep_text = await asyncio.wait_for(
                rag_svc.query(
                    _PREP_QUERIES[specialty],
                    language=language,
                    mode="text",
                    conversation_context=None,
                ),
                timeout=3.0,
            )
        except (asyncio.TimeoutError, Exception):
            return result

        separator = _PREP_SEPARATOR.get(language, _PREP_SEPARATOR["en"])
        result.message = result.message + separator + prep_text
    except Exception:
        pass
    return result


def _should_offer_booking(message: str) -> bool:
    """
    True when an informational query is adjacent to booking intent.
    """
    message_lower = message.lower()
    booking_adjacent_keywords = [
        "doctor", "dr.", "dr ", "specialist", "appointment",
        "cardiology", "general", "pediatric", "dermatology",
        "orthopedic", "raza", "malik", "iqbal", "hussain",
        "butt", "khan", "chaudhry", "siddiqui", "qureshi",
        "javed", "sheikh", "pain", "fever", "cough", "chest",
        "skin", "bone", "child", "baby", "bachay", "dard",
        "bukhaar", "doctor", "meetna", "dekhna",
    ]
    return any(keyword in message_lower for keyword in booking_adjacent_keywords)


def _is_abort_message(message: str) -> bool:
    normalized = re.sub(r"[^a-z0-9\s]", "", message.lower()).strip()
    return normalized in {
        "nvm",
        "never mind",
        "nevermind",
        "forget it",
        "leave it",
        "stop",
        "stop this",
        "cancel",
        "cancel this",
        "shush",
        "no thanks",
        "not now",
    }


def _is_reschedule_or_cancel(message: str) -> bool:
    lowered = message.lower()
    return any(word in lowered for word in ("reschedule", "reschdule", "cancel appointment", "change appointment", "move appointment"))


def _looks_like_informational_query(message: str) -> bool:
    text = message.lower()
    operational_words = (
        "book",
        "schedule",
        "reschedule",
        "cancel",
        "confirm appointment",
        "move my appointment",
        "available",
        "doctor",
        "doctors",
    )
    informational_words = (
        "opening hour",
        "open",
        "timing",
        "clinic hour",
        "visiting hour",
        "policy",
        "parking",
        "bring",
        "document",
        "cnic",
        "insurance",
        "payment",
        "fee",
        "cost",
        "medical record",
        "prescription",
        "pharmacy",
        "emergency",
        "wheelchair",
        "accessible",
        "language",
        "qualification",
        "report",
        "digital",
    )
    return any(word in text for word in informational_words) and not any(
        word in text for word in operational_words
    )


class AgentOrchestrator:
    """Routes incoming requests via intent classification."""

    async def handle_booking(
        self,
        transcript: str,
        session_id: str,
        lang: str = "en",
        mode: str = "text",
        redis=None,
    ) -> AgentResponse:
        """
        Process a text or voice request.

        Routes INFORMATIONAL queries (clinic policies, doctor bios, FAQs,
        preparation instructions, insurance, etc.) to the RAG service.
        Routes OPERATIONAL queries (appointments, slots, wait times,
        rescheduling, cancellations) to the BookingAgent.

        Args:
            transcript: The patient's text message or transcribed speech.
            session_id: Unique session identifier.
            lang: Detected language code ("en" or "ur").
            mode: "text" for chat, "voice" for voice pipeline.

        Returns:
            AgentResponse from RAG service or BookingAgent.
        """
        lowered = transcript.lower().strip()
        if any(phrase in lowered for phrase in ("talk to an agent", "contact agent", "human agent", "representative")):
            return AgentResponse(
                message="Sure. Please use the Contact Agent option and share a short message, and our team will follow up.",
                appointment_data=None,
                intent="contact_agent",
            )

        booking_state = await get_booking_state(redis, session_id) if redis else {}

        if booking_state.get("active") and _is_abort_message(transcript):
            if redis:
                await clear_booking_state(redis, session_id)
            return AgentResponse(
                message="No problem. I paused that appointment request. How else can I help?",
                appointment_data=None,
                intent="booking_cancelled",
            )

        if booking_state.get("active"):
            if _looks_like_informational_query(transcript):
                intent = "INFORMATIONAL"
                if redis:
                    await clear_booking_state(redis, session_id)
            else:
                intent = "OPERATIONAL"
        elif _is_reschedule_or_cancel(transcript):
            intent = "OPERATIONAL"
        else:
            intent = await route_intent(transcript)

        logger.info(
            "Orchestrator intent=%s session=%s lang=%s mode=%s",
            intent,
            session_id,
            lang,
            mode,
        )

        if intent == "INFORMATIONAL":
            try:
                conversation_context = await get_history(redis, session_id) if redis else []
            except Exception:
                conversation_context = []

            try:
                response_text = await rag_service.query(
                    transcript,
                    language=lang,
                    mode=mode,
                    conversation_context=conversation_context,
                )
            except Exception as exc:
                logger.exception(
                    "RAG route failed; returning safe fallback session=%s mode=%s: %s",
                    session_id,
                    mode,
                    exc,
                )
                response_text = (
                    "I don't have that specific information right now. "
                    "Please call 0800-MEDIFLOW."
                )

            if mode != "voice" and _should_offer_booking(transcript):
                response_text += (
                    "\n\nWould you like me to check available slots?"
                    if lang == "en"
                    else "\n\nکیا میں آپ کے لیے دستیاب وقت چیک کروں؟"
                )

            return AgentResponse(
                message=response_text,
                appointment_data=None,
                intent="informational_query",
            )

        if intent == "BOTH":
            try:
                conversation_context = await get_history(redis, session_id) if redis else []
            except Exception:
                conversation_context = []

            rag_task = asyncio.create_task(
                rag_service.query(
                    transcript,
                    language=lang,
                    mode=mode,
                    conversation_context=conversation_context,
                )
            )

            PROM_AGENT_STEPS.labels(agent="booking", tool="run").inc()
            agent = BookingAgent(redis=redis) if redis is not None else booking_agent
            booking_task = asyncio.create_task(
                agent.run(
                    message=transcript,
                    session_id=session_id,
                    lang=lang,
                    mode=mode,
                )
            )

            rag_answer, booking_result = await asyncio.gather(
                rag_task, booking_task, return_exceptions=True
            )

            if isinstance(booking_result, TypeError):
                try:
                    booking_result = await agent.run(transcript, session_id, lang, mode)
                except Exception as exc:
                    booking_result = exc

            if isinstance(booking_result, Exception):
                rag_text = rag_answer if isinstance(rag_answer, str) else (
                    "I could not find that information. Please call 0800-MEDIFLOW."
                )
                return AgentResponse(message=rag_text, appointment_data=None)

            if isinstance(rag_answer, Exception) or not isinstance(rag_answer, str):
                return await _append_prep_info(booking_result, lang, rag_service)

            separator = "\n\n─────────────────────────\n"
            booking_result.message = rag_answer + separator + booking_result.message
            return await _append_prep_info(booking_result, lang, rag_service)

        # OPERATIONAL -> BookingAgent
        PROM_AGENT_STEPS.labels(agent="booking", tool="run").inc()
        try:
            agent = BookingAgent(redis=redis) if redis is not None else booking_agent
            result = await agent.run(
                message=transcript,
                session_id=session_id,
                lang=lang,
                mode=mode,
            )
        except TypeError:
            # Fallback if teammate's BookingAgent uses a slightly different signature
            agent = BookingAgent(redis=redis) if redis is not None else booking_agent
            result = await agent.run(
                transcript,
                session_id,
                lang,
                mode,
            )
        return await _append_prep_info(result, lang, rag_service)
            
    async def run_ops_monitor(
        self,
        trigger: str = "scheduled",
        context: Optional[Dict[str, Any]] = None,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        from agents.ops_agent import ops_monitor_agent
        PROM_AGENT_STEPS.labels(agent="ops_monitor", tool="run").inc()
        return await ops_monitor_agent.run(
            trigger=trigger,
            context=context or {},
            db=db,
        )


orchestrator = AgentOrchestrator()
