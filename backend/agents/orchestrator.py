"""
Agent Orchestrator
==================

Single entry point for both chat and voice requests.
Routes INFORMATIONAL queries to RAG, OPERATIONAL queries to BookingAgent.
"""

from __future__ import annotations

import logging

from agents.booking_agent import AgentResponse, booking_agent
from agents.booking_agent import BookingAgent
from services.intent_router import route_intent
from services.rag_service import rag_service
from services.redis_memory import clear_booking_state, get_booking_state
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from prometheus_client import Counter

logger = logging.getLogger(__name__)

PROM_AGENT_STEPS = Counter(
    "mediflow_agent_steps_total",
    "Agent tool calls",
    ["agent", "tool"]
)


def _is_abort_message(message: str) -> bool:
    lowered = message.lower().strip()
    return lowered in {
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

        intent = await route_intent(transcript)
        if booking_state.get("active") and intent == "INFORMATIONAL":
            if redis:
                await clear_booking_state(redis, session_id)
        elif booking_state.get("active") or _is_reschedule_or_cancel(transcript):
            intent = "OPERATIONAL"

        logger.info(
            "Orchestrator intent=%s session=%s lang=%s mode=%s",
            intent,
            session_id,
            lang,
            mode,
        )

        if intent == "INFORMATIONAL":
            try:
                response_text = await rag_service.query(transcript, language=lang, mode=mode)
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
            return AgentResponse(
                message=response_text,
                appointment_data=None,
                intent="informational_query",
            )

        # OPERATIONAL -> BookingAgent
        try:
            agent = BookingAgent(redis=redis) if redis is not None else booking_agent
            return await agent.run(
                message=transcript,
                session_id=session_id,
                lang=lang,
                mode=mode,
            )
        except TypeError:
            # Fallback if teammate's BookingAgent uses a slightly different signature
            agent = BookingAgent(redis=redis) if redis is not None else booking_agent
            return await agent.run(
                transcript,
                session_id,
                lang,
                mode,
            )
            
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
