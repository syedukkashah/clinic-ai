"""
intent_router.py

Classifies a user message as OPERATIONAL or INFORMATIONAL.

OPERATIONAL  → Booking Agent (DB tools, appointments, slots, wait times)
INFORMATIONAL → RAG service (clinic docs, policies, FAQs, doctor bios)

Defaults to OPERATIONAL on any failure — the Booking Agent is the safe fallback.
"""

import logging
from services.llm_router import llm_router
from prometheus_client import Counter

logger = logging.getLogger(__name__)

PROM_INTENT_ROUTE = Counter(
    "mediflow_intent_route_total",
    "Intent routing decisions",
    ["intent"]
)

ROUTING_PROMPT = """Classify this patient message into exactly ONE category.

OPERATIONAL: booking appointment, rescheduling, cancelling,
checking wait time, doctor availability, queue status,
viewing or managing appointments, complaint about a specific visit.

INFORMATIONAL: clinic hours, opening times, doctor qualifications,
doctor specialization, doctor biography, clinic policies,
preparation instructions before appointment, what to bring,
insurance questions, payment methods, consultation fees,
FAQs, visiting guidelines, parking, emergency guidance,
pharmacy questions, medical certificates, prescription policies,
medical records policy.

Reply with ONLY the single word: OPERATIONAL or INFORMATIONAL

Message: {message}"""


async def route_intent(message: str) -> str:
    """
    Returns 'OPERATIONAL' or 'INFORMATIONAL'.
    Defaults to 'OPERATIONAL' on any failure.
    """
    try:
        prompt = ROUTING_PROMPT.format(message=message)
        resp = await llm_router.call(
            messages=[{"role": "user", "content": prompt}],
            system="You are a precise intent classifier. Reply only with OPERATIONAL or INFORMATIONAL.",
            task_type="extraction",
        )
        text = resp.text.strip().upper() if resp and resp.text else ""
        intent = "INFORMATIONAL" if "INFORMATIONAL" in text else "OPERATIONAL"
    except Exception as e:
        logger.warning(f"intent_router: LLM call failed ({e}), defaulting to OPERATIONAL")
        intent = "OPERATIONAL"

    PROM_INTENT_ROUTE.labels(intent=intent).inc()
    return intent
