"""
Agent Orchestrator
==================

Single entry point for both chat and voice requests.
Routes INFORMATIONAL queries to RAG, OPERATIONAL queries to BookingAgent.
"""

from __future__ import annotations

import logging

from agents.booking_agent import AgentResponse, booking_agent
from services.intent_router import route_intent
from services.rag_service import rag_service
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from prometheus_client import Counter

logger = logging.getLogger(__name__)

PROM_AGENT_STEPS = Counter(
    "mediflow_agent_steps_total",
    "Agent tool calls",
    ["agent", "tool"]
)

class AgentOrchestrator:
    """Routes incoming requests via intent classification."""

    async def handle_booking(
        self,
        transcript: str,
        session_id: str,
        lang: str = "en",
        mode: str = "text",
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
        intent = await route_intent(transcript)
        logger.info(
            "Orchestrator intent=%s session=%s lang=%s mode=%s",
            intent,
            session_id,
            lang,
            mode,
        )

        if intent == "INFORMATIONAL":
            response_text = await rag_service.query(transcript, language=lang, mode=mode)
            return AgentResponse(
                message=response_text,
                appointment_data=None,
            )

        # OPERATIONAL → BookingAgent
        try:
            return await booking_agent.run(
                message=transcript,
                session_id=session_id,
                lang=lang,
                mode=mode,
            )
        except TypeError:
            # Fallback if teammate's BookingAgent uses a slightly different signature
            return await booking_agent.run(
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