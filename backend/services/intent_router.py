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
listing doctors by specialty, viewing or managing appointments,
complaint about a specific visit.

INFORMATIONAL: clinic hours, opening times, doctor qualifications,
doctor biography, clinic policies, preparation instructions before
appointment, what to bring, insurance questions, payment methods,
consultation fees, FAQs, visiting guidelines, parking, emergency
guidance, pharmacy questions, medical certificates, prescription policies,
medical records policy.

EXAMPLES:
Message: "I need to see a doctor tomorrow"
OPERATIONAL

Message: "What time do you open?"
INFORMATIONAL

Message: "Cancel my appointment for next week"
OPERATIONAL

Message: "Does Dr. Smith take insurance?"
INFORMATIONAL

Message: "List cardiologists"
OPERATIONAL

Reply with ONLY the single word: OPERATIONAL or INFORMATIONAL

Message: {message}"""


def _keyword_route(message: str) -> str | None:
    text = message.lower()
    listing_words = ("list", "show", "find", "available", "who are")
    doctor_words = (
        "doctor",
        "doctors",
        "cardiologist",
        "cardiologists",
        "pediatrician",
        "dermatologist",
        "orthopedic",
    )
    if any(word in text for word in listing_words) and any(word in text for word in doctor_words):
        return "OPERATIONAL"

    operational_words = (
        "book",
        "schedule",
        "reschedule",
        "cancel",
        "confirm appointment",
        "move my appointment",
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
    )
    if any(word in text for word in informational_words) and not any(word in text for word in operational_words):
        return "INFORMATIONAL"
    return None


async def route_intent(message: str) -> str:
    """
    Returns 'OPERATIONAL' or 'INFORMATIONAL'.
    Defaults to 'OPERATIONAL' on any failure.
    """
    keyword_intent = _keyword_route(message)
    if keyword_intent:
        PROM_INTENT_ROUTE.labels(intent=keyword_intent).inc()
        return keyword_intent

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
