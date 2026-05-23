"""
intent_router.py

Classifies a user message as OPERATIONAL, INFORMATIONAL, or BOTH.

OPERATIONAL    -> Booking Agent handles it (DB tools, appointments, slots)
INFORMATIONAL  -> RAG handles it (clinic docs, policies, FAQs)
BOTH           -> RAG answers first, then Booking Agent continues
                 (e.g. "Book Dr. Nadia Hussain, what should I bring?")

Uses Groq (fast extraction tier) for low-latency classification.
Falls back to OPERATIONAL on any failure to avoid breaking booking flow.
"""

from services.llm_router import llm_router

_ROUTING_PROMPT = """
Classify the patient message into exactly ONE of three categories:

OPERATIONAL
  The patient wants to DO something with an appointment:
  book, cancel, reschedule, check wait time, check availability,
  see my upcoming appointments, modify an existing booking,
  what slots are available, is [doctor] available [date/time],
  I want to see a doctor [date], book me an appointment.

INFORMATIONAL
  The patient wants to KNOW something about the clinic:
  clinic hours, clinic location, doctor qualifications,
  what does [doctor] specialize in, preparation before appointment,
  what should I bring, do you accept [insurance], payment methods,
  cancellation policy, fees, FAQs, parking, pharmacy, emergency info,
  which doctor should I see for [symptom], visiting guidelines.

BOTH
  The message contains BOTH an operational request AND an
  informational question in the same message:
  "Book me an appointment with Dr. Nadia Hussain and what should I bring?"
  "I want to see cardiology tomorrow, how much does it cost?"
  "Schedule an appointment and tell me about the cancellation policy"
  "I need to book and also want to know what to bring"

RULES:
- If in doubt between OPERATIONAL and INFORMATIONAL, choose OPERATIONAL.
- BOTH requires an explicit informational question alongside a booking action.
  Do not use BOTH just because a doctor name is mentioned.
- "Is Dr. X available?" = OPERATIONAL (checking availability, not asking about qualifications).
- "Tell me about Dr. X" = INFORMATIONAL.
- "Book Dr. X, is she good?" = BOTH.

Reply with ONLY ONE WORD: OPERATIONAL, INFORMATIONAL, or BOTH.

Message: {message}
"""

_VALID_INTENTS = {"OPERATIONAL", "INFORMATIONAL", "BOTH"}
_DEFAULT_INTENT = "OPERATIONAL"


def _keyword_route(message: str) -> str | None:
    text = message.lower()
    operational_words = (
        "book",
        "schedule",
        "reschedule",
        "cancel appointment",
        "confirm appointment",
        "move my appointment",
        "available",
        "availability",
        "slots",
        "list",
        "show",
    )
    informational_words = (
        "opening hour",
        "clinic timing",
        "timing",
        "hours",
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
        "qualification",
        "what should",
        "which doctor",
    )
    if any(word in text for word in operational_words) and any(word in text for word in informational_words):
        return "BOTH"
    if any(word in text for word in informational_words) and not any(word in text for word in operational_words):
        return "INFORMATIONAL"
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
    return None


async def route_intent(message: str) -> str:
    """
    Returns 'OPERATIONAL', 'INFORMATIONAL', or 'BOTH'.

    Never raises - falls back to OPERATIONAL on any error.
    This function is called on EVERY message, so it must be fast.
    Uses Groq (extraction tier) for lowest latency.
    """
    if not message or not message.strip():
        return _DEFAULT_INTENT

    keyword_intent = _keyword_route(message)
    if keyword_intent:
        return keyword_intent

    prompt = _ROUTING_PROMPT.format(message=message.strip())

    intent = await _classify(prompt)
    if intent in _VALID_INTENTS:
        return intent

    simple_prompt = (
        f"Is this message asking to book/cancel/reschedule an appointment "
        f"(OPERATIONAL), asking for clinic information (INFORMATIONAL), "
        f"or both (BOTH)? Reply with only one word.\n\nMessage: {message}"
    )
    intent = await _classify(simple_prompt)
    if intent in _VALID_INTENTS:
        return intent

    return _DEFAULT_INTENT


async def _classify(prompt: str) -> str:
    """
    Makes a single LLM call and returns the cleaned intent string.
    Returns empty string on any failure.
    """
    try:
        resp = await llm_router.call(
            messages=[{"role": "user", "content": prompt}],
            system=(
                "You are a precise medical appointment intent classifier. "
                "Reply with only one word: OPERATIONAL or INFORMATIONAL or BOTH."
            ),
            task_type="extraction",
        )
        if not resp or not resp.text:
            return ""
        text = resp.text.strip().upper()
        for intent in _VALID_INTENTS:
            if intent in text:
                return intent
        return ""
    except Exception:
        return ""
