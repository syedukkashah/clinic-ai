"""
AgentOrchestrator — thin routing class.
Lives inside the FastAPI process, NOT a separate service.
All routes call this, never agents directly.
"""

import logging
from services.llm_router import llm_router
from db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    def __init__(self, redis=None):
        self.redis = redis

    async def handle_booking(
        self,
        message: str,
        session_id: str,
        language: str = "en",
        mode: str = "text",
    ):
        from agents.booking_agent import process_chat_message
        return await process_chat_message(
            user_id=session_id,
            message=message,
            redis_client=self.redis,
            language=language,
            mode=mode,
        )


orchestrator = AgentOrchestrator()