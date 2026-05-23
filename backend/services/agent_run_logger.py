from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from db.models import AgentRun
from db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


def providers_from_steps(steps: Optional[List[Dict[str, Any]]]) -> List[str]:
    providers = []
    for step in steps or []:
        provider = step.get("provider")
        if provider and provider not in providers:
            providers.append(str(provider))
    return providers


async def record_agent_run(
    *,
    agent: str,
    session_id: Optional[str] = None,
    mode: Optional[str] = None,
    language: Optional[str] = None,
    trigger: Optional[str] = None,
    outcome: Optional[str] = None,
    tool_calls: Optional[List[Dict[str, Any]]] = None,
    duration_ms: Optional[int] = None,
    summary: Optional[str] = None,
    started_at: Optional[datetime] = None,
    completed_at: Optional[datetime] = None,
) -> None:
    try:
        async with AsyncSessionLocal() as db:
            run = AgentRun(
                id=str(uuid.uuid4()),
                agent=agent,
                session_id=session_id,
                mode=mode,
                language=language,
                trigger=trigger,
                outcome=outcome,
                steps_count=len(tool_calls or []),
                duration_ms=duration_ms,
                providers_used=providers_from_steps(tool_calls),
                tool_calls=tool_calls or [],
                summary=summary,
                started_at=started_at or datetime.now(timezone.utc),
                completed_at=completed_at or datetime.now(timezone.utc),
            )
            db.add(run)
            await db.commit()
    except Exception as exc:
        logger.warning("Failed to persist %s agent run: %s", agent, exc)


def add_agent_run_to_session(
    db,
    *,
    agent: str,
    session_id: Optional[str] = None,
    mode: Optional[str] = None,
    language: Optional[str] = None,
    trigger: Optional[str] = None,
    outcome: Optional[str] = None,
    tool_calls: Optional[List[Dict[str, Any]]] = None,
    duration_ms: Optional[int] = None,
    summary: Optional[str] = None,
    started_at: Optional[datetime] = None,
    completed_at: Optional[datetime] = None,
) -> AgentRun:
    run = AgentRun(
        id=str(uuid.uuid4()),
        agent=agent,
        session_id=session_id,
        mode=mode,
        language=language,
        trigger=trigger,
        outcome=outcome,
        steps_count=len(tool_calls or []),
        duration_ms=duration_ms,
        providers_used=providers_from_steps(tool_calls),
        tool_calls=tool_calls or [],
        summary=summary,
        started_at=started_at or datetime.now(timezone.utc),
        completed_at=completed_at or datetime.now(timezone.utc),
    )
    db.add(run)
    return run
