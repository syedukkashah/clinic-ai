"""
Agent Orchestrator
==================

Single entry point for both chat and voice requests.
For now, everything routes to BookingAgent.
RAG/intent routing can be added later without changing callers.
"""

from __future__ import annotations

import logging

from agents.booking_agent import AgentResponse, booking_agent

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Routes incoming requests to the booking agent for now."""

    async def handle_booking(
        self,
        transcript: str,
        session_id: str,
        lang: str = "en",
        mode: str = "text",
    ) -> AgentResponse:
        """
        Process a text or voice request.

        Args:
            transcript: The patient's text message or transcribed speech.
            session_id: Unique session identifier.
            lang: Detected language code ("en" or "ur").
            mode: "text" for chat, "voice" for voice pipeline.

        Returns:
            AgentResponse from BookingAgent.
        """
        logger.info(
            "Orchestrator routing to BookingAgent — session=%s lang=%s mode=%s",
            session_id,
            lang,
            mode,
        )

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


orchestrator = AgentOrchestrator()