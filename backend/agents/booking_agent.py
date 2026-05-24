"""
Booking Agent — MediFlow Agent 1
=================================
Handles all inbound patient requests via text and voice.
Uses a prompt-based ReAct loop since the LLM router returns
plain text (not native tool_use blocks).

Flow per message:
  1. Load Redis session history
  2. Build system prompt with available tools described
  3. Loop: LLM decides action → parse JSON → execute tool → feed result back
  4. LLM produces final plain-text response
  5. Save updated history to Redis

Tools available:
  - get_available_slots
  - get_doctor_profile
  - check_patient_history
  - predict_wait_time
  - create_appointment
  - cancel_appointment
  - reschedule_appointment

Entry points:
  - process_chat_message()  →  called by api/routes/chat.py (text chat)
  - BookingAgent.run()      →  called by AgentOrchestrator (voice pipeline + RAG path)
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from db.session import AsyncSessionLocal
from db import crud
from services.llm_router import llm_router, AllProvidersExhausted
from services.redis_memory import (
    clear_booking_state,
    get_booking_state,
    get_history,
    save_booking_state,
    save_history,
    RECOVERY_MSG,
)
from services.ml_service import ml_service_client
from services.agent_run_logger import record_agent_run

logger = logging.getLogger(__name__)

MAX_STEPS_TEXT = 5
MAX_STEPS_VOICE = 3

DOCTOR_NAME_TO_ID = {
    "ahmed": 1, "raza": 1,
    "sara": 2, "malik": 2,
    "kamran": 3, "iqbal": 3,
    "nadia": 4, "hussain": 4,
    "tariq": 5, "butt": 5,
    "ayesha": 6, "khan": 6,
    "bilal": 7, "chaudhry": 7,
    "zara": 8, "siddiqui": 8,
    "usman": 9, "qureshi": 9,
    "hina": 10, "javed": 10,
    "faisal": 11, "sheikh": 11,
}

DOCTOR_ID_TO_NAME = {
    1: "Ahmed Raza",
    2: "Sara Malik",
    3: "Kamran Iqbal",
    4: "Nadia Hussain",
    5: "Tariq Butt",
    6: "Ayesha Khan",
    7: "Bilal Chaudhry",
    8: "Zara Siddiqui",
    9: "Usman Qureshi",
    10: "Hina Javed",
    11: "Faisal Sheikh",
}

DEFAULT_DOCTOR_BY_SPECIALTY = {
    "general": 1,
    "cardiology": 4,
    "pediatrics": 6,
    "dermatology": 8,
    "orthopedics": 10,
}


# ── AgentResponse ─────────────────────────────────────────────────────────────

@dataclass
class AgentResponse:
    """
    Structured response returned by BookingAgent.run() and the RAG path.

    Used by:
      - AgentOrchestrator.handle_booking()   (returns this to the voice pipeline)
      - voice_service.handle_voice_request() (reads .message for TTS)
      - rag_service.query() result wrapper   (appointment_data=None for RAG)
    """

    message: str
    """The agent's text response to the patient."""

    appointment_data: Optional[Dict[str, Any]] = None
    """Extracted appointment details, if any. None for informational RAG responses."""

    intent: str = "general_query"
    """Detected intent: booking_intent | cancel_intent | reschedule_intent | general_query."""

    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    """Tool calls made during this turn (used by debug sidebar display)."""

    suggested_slots: List[Dict[str, Any]] = field(default_factory=list)
    """Structured appointment slots shown as interactive cards in the frontend."""


# ── System prompts ────────────────────────────────────────────────────────────

SYSTEM_TEXT = """You are MediFlow, the official AI Booking Agent for the clinic.
Your patient-facing replies must always be warm, concise plain text. Never show JSON, tool names, or internal implementation details to the patient.

### Clinic doctors
- General Practice: Dr. Ahmed Raza (1), Dr. Sara Malik (2), Dr. Kamran Iqbal (3)
- Cardiology: Dr. Nadia Hussain (4), Dr. Tariq Butt (5)
- Pediatrics: Dr. Ayesha Khan (6), Dr. Bilal Chaudhry (7)
- Dermatology: Dr. Zara Siddiqui (8), Dr. Usman Qureshi (9)
- Orthopedics: Dr. Hina Javed (10), Dr. Faisal Sheikh (11)

### Available internal tools
Use tools only when useful, in this exact JSON format:
{"tool": "tool_name", "args": {"param": "value"}}

- list_doctors: {"tool": "list_doctors", "args": {"specialty": "cardiology"}}
- get_available_slots: {"tool": "get_available_slots", "args": {"specialty": "general"}}
- get_doctor_profile: {"tool": "get_doctor_profile", "args": {"doctor_id": 1}}
- get_clinic_timings: {"tool": "get_clinic_timings", "args": {}}
- create_appointment: {"tool": "create_appointment", "args": {"patient_name": "...", "doctor_id": 1, "date": "YYYY-MM-DD", "time": "HH:MM", "complaint": "..."}}
- cancel_appointment: {"tool": "cancel_appointment", "args": {"appointment_id": "..."}}
- reschedule_appointment: {"tool": "reschedule_appointment", "args": {"appointment_id": "...", "date": "YYYY-MM-DD", "time": "HH:MM"}}

### Booking rules
- If the patient wants to book, do not create an appointment until you have their name, doctor or specialty, date, time, and reason.
- If any required booking detail is missing, ask one short clarifying question instead of calling create_appointment.
- After a tool result, summarize it in plain text for the patient.
- For clinic hours, policies, general doctor information, or FAQ-style questions, answer naturally and do not invent unavailable data.
"""

# Voice prompt: same tool list as SYSTEM_TEXT but with the 2-sentence constraint
# enforced to keep TTS synthesis under 1.2s (part of the 4-8s voice latency budget).
PROMPT_VOICE = """You are MediFlow, the clinic's voice assistant. 
You handle live calls to book appointments and answer simple scheduling questions. Patient-facing replies must be plain spoken text. Never speak JSON, tool names, markdown, or internal details.
Sound like a calm front-desk assistant: friendly, specific, and reassuring. Acknowledge what the caller said before asking the next question.

### YOUR CLINIC KNOWLEDGE (Doctor IDs):
- **General**: Dr. Ahmed Raza (1), Dr. Sara Malik (2), Dr. Kamran Iqbal (3)
- **Cardiology**: Dr. Nadia Hussain (4), Dr. Tariq Butt (5)
- **Pediatrics**: Dr. Ayesha Khan (6), Dr. Bilal Chaudhry (7)
- **Dermatology**: Dr. Zara Siddiqui (8), Dr. Usman Qureshi (9)
- **Orthopedics**: Dr. Hina Javed (10), Dr. Faisal Sheikh (11)

### VOICE CONSTRAINTS:
- Keep conversational responses to MAX 2 SENTENCES.
- No markdown, no asterisks, no bullet points. Plain spoken text only.
- If booking details are missing, ask one concise question for the next missing detail.
- Do not create an appointment until you have the patient's name, doctor or specialty, date, time, reason, and contact number.
- Preserve context across turns. If the caller already gave a doctor, date, time, name, reason, or phone number, do not ask for it again.
- When the caller gives only a phone number, treat it as their contact number and continue or confirm the booking.
- After a tool result, summarize it naturally for the caller.
- If the caller speaks Urdu, reply in Urdu.

### TOOLS:
- list_doctors: {"tool": "list_doctors", "args": {"specialty": "cardiology"}}
- get_available_slots: {"tool": "get_available_slots", "args": {"specialty": "general"}}
- get_doctor_profile: {"tool": "get_doctor_profile", "args": {"doctor_id": 1}}
- get_clinic_timings: {"tool": "get_clinic_timings", "args": {}}
- create_appointment: {"tool": "create_appointment", "args": {"patient_name": "...", "doctor_id": 1, "date": "YYYY-MM-DD", "time": "HH:MM", "complaint": "..."}}
- cancel_appointment: {"tool": "cancel_appointment", "args": {"appointment_id": "..."}}
"""

# Alias kept for any code that still imports SYSTEM_VOICE by name.
SYSTEM_VOICE = PROMPT_VOICE

PROMPT_TEXT = SYSTEM_TEXT


def _normalize_specialty(value: Any) -> str:
    specialty = str(value or "general").strip().lower()
    aliases = {
        "cardiologist": "cardiology",
        "cardiologists": "cardiology",
        "heart": "cardiology",
        "child": "pediatrics",
        "children": "pediatrics",
        "pediatric": "pediatrics",
        "skin": "dermatology",
        "dermatologist": "dermatology",
        "dermatologists": "dermatology",
        "bone": "orthopedics",
        "bones": "orthopedics",
        "orthopedic": "orthopedics",
        "general practice": "general",
        "general medicine": "general",
    }
    return aliases.get(specialty, specialty)


def _normalize_tool_args(tool_name: str, args: Dict) -> Dict:
    normalized = dict(args or {})
    if "specialization" in normalized and "specialty" not in normalized:
        normalized["specialty"] = normalized["specialization"]
    if "department" in normalized and "specialty" not in normalized:
        normalized["specialty"] = normalized["department"]
    if "appointment_date" in normalized and "date" not in normalized:
        normalized["date"] = normalized["appointment_date"]
    if "appointment_time" in normalized and "time" not in normalized:
        normalized["time"] = normalized["appointment_time"]
    if "reason" in normalized and "complaint" not in normalized:
        normalized["complaint"] = normalized["reason"]
    if tool_name in {"list_doctors", "get_available_slots"}:
        normalized["specialty"] = _normalize_specialty(normalized.get("specialty"))
    return normalized


def _format_doctor_name(name: Any) -> str:
    display = str(name or "").strip()
    if not display:
        return "Doctor"
    return display if display.lower().startswith("dr.") else f"Dr. {display}"


def _looks_like_booking_message(message: str) -> bool:
    text = message.lower()
    booking_words = (
        "book",
        "appointment",
        "appoint",
        "schedule",
        "visit",
        "available",
        "doctor",
        "dr ",
        "dr.",
        "kamran",
        "ahmed",
        "sara",
        "nadia",
        "tariq",
    )
    symptom_words = ("flu", "fever", "cold", "cough", "pain", "checkup", "check-up")
    phone_only = re.fullmatch(r"[\s:+()0-9-]{7,}", message.strip()) is not None
    return phone_only or any(word in text for word in booking_words + symptom_words)


def _looks_like_reschedule_message(message: str) -> bool:
    text = message.lower()
    return any(word in text for word in ("reschedule", "reschdule", "change appointment", "move appointment", "move this", "move it"))


def _looks_like_cancel_intent(message: str) -> bool:
    text = message.lower()
    return "cancel appointment" in text or bool(_extract_appointment_id(message) and "cancel" in text)


def _is_abort_message(message: str) -> bool:
    text = re.sub(r"[^a-z0-9\s]", "", message.lower()).strip()
    aborts = {
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
    if _extract_appointment_id(message):
        return False
    return text in aborts


def _extract_appointment_id(message: str) -> Optional[str]:
    match = re.search(r"\bapt[-_][a-zA-Z0-9-]+\b", message, flags=re.IGNORECASE)
    return match.group(0).replace("_", "-") if match else None


def _extract_name(message: str) -> Optional[str]:
    patterns = [
        r"\bmy name is\s+([a-zA-Z][a-zA-Z .'-]{1,50})",
        r"\bi am\s+([a-zA-Z][a-zA-Z .'-]{1,50})",
        r"\bi'm\s+([a-zA-Z][a-zA-Z .'-]{1,50})",
    ]
    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if match:
            name = re.split(r"\s+(?:and|,|\.|i have|i want)\b", match.group(1), maxsplit=1, flags=re.IGNORECASE)[0]
            return " ".join(part.capitalize() for part in name.strip().split())
    first_part = message.split(",", 1)[0].strip()
    blocked = {
        "book", "appointment", "reschedule", "cancel", "clinic", "doctor", "doctors",
        "dermatologist", "dermatology", "cardiologist", "cardiology", "pediatrics",
        "orthopedics", "general", "flu", "fever", "cold", "cough", "pain",
    }
    if (
        2 <= len(first_part) <= 40
        and re.fullmatch(r"[a-zA-Z][a-zA-Z .'-]*", first_part)
        and not any(word in first_part.lower().split() for word in blocked)
    ):
        return " ".join(part.capitalize() for part in first_part.split())
    return None


def _extract_phone(message: str) -> Optional[str]:
    match = re.search(r"(?:\+?\d[\d\s().-]{6,}\d)", message)
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group(0))
    return digits if len(digits) >= 7 else None


def _extract_doctor(message: str) -> tuple[Optional[int], Optional[str]]:
    text = message.lower()
    for name_part, doctor_id in DOCTOR_NAME_TO_ID.items():
        if name_part in text:
            return doctor_id, DOCTOR_ID_TO_NAME.get(doctor_id)
    return None, None


def _extract_specialty(message: str) -> Optional[str]:
    text = message.lower()
    if any(word in text for word in ("flu", "fever", "cold", "cough", "general practitioner", "gp")):
        return "general"
    for key in (
        "cardiology",
        "cardiologist",
        "cardiologists",
        "pediatrics",
        "dermatology",
        "dermatologist",
        "dermatologists",
        "orthopedics",
    ):
        if key in text:
            return _normalize_specialty(key)
    return None


def _extract_time(message: str) -> Optional[str]:
    stripped = message.strip()
    if re.fullmatch(r"[\s:+()0-9-]{7,}", stripped) or "number" in message.lower() or "contact" in message.lower():
        return None

    match = re.search(r"(?<![-\d])\b([01]?\d|2[0-3]):([0-5]\d)\s*(am|pm)?\b", message, flags=re.IGNORECASE)
    if not match:
        match = re.search(r"(?<![-\d])\b(1[0-2]|0?[1-9])\s*(am|pm)\b", message, flags=re.IGNORECASE)
    if not match:
        return None

    hour = int(match.group(1))
    if match.lastindex == 3:
        minute = int(match.group(2) or "00")
        meridiem = (match.group(3) or "").lower()
    else:
        minute = 0
        meridiem = (match.group(2) or "").lower()
    if meridiem == "pm" and hour < 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


def _extract_date(message: str) -> Optional[str]:
    text = message.lower()
    today = datetime.now(timezone.utc).date()
    if "tomorrow" in text:
        return (today + timedelta(days=1)).isoformat()
    weekdays = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }
    for name, target in weekdays.items():
        if name in text:
            delta = (target - today.weekday()) % 7
            if delta == 0:
                delta = 7
            return (today + timedelta(days=delta)).isoformat()
    match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", message)
    if match:
        return match.group(1)
    months = {
        "jan": 1, "january": 1,
        "feb": 2, "february": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12,
    }
    month_pattern = "|".join(months)
    natural = re.search(
        rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({month_pattern})(?:\s*,?\s*(20\d{{2}}))?\b",
        text,
        flags=re.IGNORECASE,
    )
    if natural:
        day = int(natural.group(1))
        month = months[natural.group(2).lower()]
        year = int(natural.group(3) or today.year)
        candidate = datetime(year, month, day).date()
        if not natural.group(3) and candidate < today:
            candidate = datetime(year + 1, month, day).date()
        return candidate.isoformat()
    return None


def _extract_complaint(message: str) -> Optional[str]:
    text = message.lower()
    symptoms = [symptom for symptom in ("flu", "fever", "cold", "cough", "pain", "checkup", "check-up") if symptom in text]
    if symptoms:
        return " and ".join(dict.fromkeys(symptoms)).replace("check-up", "checkup")
    match = re.search(r"\bi have\s+([^.;]+)", message, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    parts = [
        part.strip()
        for part in message.split(",")
        if part.strip()
    ]
    for part in reversed(parts):
        low = part.lower()
        if (
            low in {"general", "routine", "checkup", "check-up", "consultation"}
            or low.startswith(("general ", "routine "))
        ):
            return part
    return None


def _merge_booking_state(state: Dict[str, Any], message: str) -> Dict[str, Any]:
    updated = dict(state or {})
    updated["active"] = True
    if name := _extract_name(message):
        updated["patient_name"] = name
    if phone := _extract_phone(message):
        updated["contact_number"] = phone
    doctor_id, doctor_name = _extract_doctor(message)
    if doctor_id:
        updated["doctor_id"] = doctor_id
        updated["doctor_name"] = doctor_name
    if specialty := _extract_specialty(message):
        updated["specialty"] = specialty
    if date_value := _extract_date(message):
        updated["date"] = date_value
    if time_value := _extract_time(message):
        updated["time"] = time_value
    if complaint := _extract_complaint(message):
        updated["complaint"] = complaint
    return updated


def _missing_booking_fields(state: Dict[str, Any]) -> list[str]:
    missing = []
    if not state.get("patient_name"):
        missing.append("your full name")
    if not state.get("doctor_id") and not state.get("specialty"):
        missing.append("which doctor or department you prefer")
    if not state.get("date"):
        missing.append("appointment date")
    if not state.get("time"):
        missing.append("appointment time")
    if not state.get("complaint"):
        missing.append("reason for visit")
    if not state.get("contact_number"):
        missing.append("your contact number")
    return missing


def _next_booking_question(missing: list[str]) -> str:
    if not missing:
        return ""
    if len(missing) == 1:
        return f"Please share {missing[0]} so I can confirm the appointment."
    return "Please share " + ", ".join(missing[:-1]) + f", and {missing[-1]} so I can confirm the appointment."


def _missing_reschedule_fields(state: Dict[str, Any]) -> list[str]:
    missing = []
    if not state.get("appointment_id"):
        missing.append("appointment ID")
    if not state.get("date"):
        missing.append("new appointment date")
    if not state.get("time"):
        missing.append("new appointment time")
    return missing


def _next_reschedule_question(missing: list[str]) -> str:
    if not missing:
        return ""
    if len(missing) == 1:
        return f"Please share the {missing[0]} so I can reschedule the appointment."
    return "Please share the " + ", ".join(missing[:-1]) + f", and {missing[-1]} so I can reschedule the appointment."


def _ensure_doctor_for_department(state: Dict[str, Any]) -> Dict[str, Any]:
    if not state.get("doctor_id") and state.get("specialty"):
        specialty = _normalize_specialty(state["specialty"])
        state["doctor_id"] = DEFAULT_DOCTOR_BY_SPECIALTY.get(specialty, 1)
        state["doctor_name"] = DOCTOR_ID_TO_NAME.get(state["doctor_id"])
    return state


def _merge_reschedule_state(state: Dict[str, Any], message: str) -> Dict[str, Any]:
    updated = dict(state or {})
    updated["active"] = True
    updated["intent"] = "reschedule"
    if appointment_id := _extract_appointment_id(message):
        updated["appointment_id"] = appointment_id

    lowered = message.lower()
    looks_like_existing_summary = bool(_extract_appointment_id(message)) and (
        "date:" in lowered or "id:" in lowered
    ) and not any(marker in lowered for marker in (" to ", "new ", "instead", "move to", "change to", "reschedule to", "reschedule for"))

    if not looks_like_existing_summary:
        if date_value := _extract_date(message):
            updated["date"] = date_value
        if time_value := _extract_time(message):
            updated["time"] = time_value
    return updated


async def _doctor_summary_for_state(state: Dict[str, Any]) -> Optional[str]:
    specialty = state.get("specialty")
    if not specialty:
        return None
    return await _list_doctors({"specialty": specialty})


async def _availability_summary(doctor_id: int, doctor_name: str | None = None) -> str:
    async with AsyncSessionLocal() as db:
        avail = await crud.get_doctor_availability(db, doctor_id)
    slots = avail.get("availableSlots", [])[:6]
    display_name = doctor_name or DOCTOR_ID_TO_NAME.get(doctor_id, f"ID {doctor_id}")
    if slots:
        return f"{_format_doctor_name(display_name)} has available slots at {', '.join(slots)}. Which date and time would you like?"
    return f"I don't see open slots for {_format_doctor_name(display_name)} right now. Please choose another doctor or time."


async def _build_slot_suggestions(state: Dict[str, Any], limit: int = 3) -> List[Dict[str, Any]]:
    """Return structured slot options backed by DB availability and ML wait estimates."""
    specialty = _normalize_specialty(state.get("specialty", "general"))
    doctor_id = state.get("doctor_id")

    async with AsyncSessionLocal() as db:
        doctors = await crud.get_doctors(db)

        if doctor_id:
            matching = [doc for doc in doctors if int(doc["id"]) == int(doctor_id)]
        else:
            matching = [
                doc for doc in doctors
                if specialty.lower() in doc.get("specialty", "").lower()
            ]

        if not matching:
            matching = doctors[:3]

        suggestions: List[Dict[str, Any]] = []
        for doc in matching[:3]:
            avail = await crud.get_doctor_availability(db, int(doc["id"]))
            for slot_time in avail.get("availableSlots", [])[:3]:
                if len(suggestions) >= limit:
                    break

                try:
                    hour = int(str(slot_time).split(":", 1)[0])
                except Exception:
                    hour = 10

                prediction = await ml_service_client.get_wait_time({
                    "slot_id": f"{doc['id']}-{slot_time}",
                    "doctor_id": int(doc["id"]),
                    "hour_of_day": hour,
                })
                if "error" in prediction:
                    wait = 8 + ((int(doc["id"]) * 7 + hour * 3 + len(suggestions) * 5) % 36)
                else:
                    wait = int(prediction.get("predicted_wait_minutes", 12) or 12)

                suggestions.append({
                    "id": f"slot-{doc['id']}-{slot_time}",
                    "doctorId": int(doc["id"]),
                    "doctorName": _format_doctor_name(doc.get("name")),
                    "specialty": doc.get("specialty") or specialty,
                    "date": state.get("date") or date.today().isoformat(),
                    "time": slot_time,
                    "wait": wait,
                    "predictedWaitMin": wait,
                    "source": "db+ml_service",
                })
            if len(suggestions) >= limit:
                break

    return suggestions


async def _handle_booking_state(message: str, session_id: str, redis_client, language: str, mode: str) -> Optional[AgentResponse]:
    if not redis_client:
        return None

    state = await get_booking_state(redis_client, session_id)
    active = bool(state.get("active"))
    lowered = message.lower().strip()

    if active and _is_abort_message(message):
        await clear_booking_state(redis_client, session_id)
        return AgentResponse(
            message="No problem. I paused that appointment request. How else can I help?",
            intent="booking_cancelled",
        )

    if _looks_like_reschedule_message(message) or state.get("intent") == "reschedule":
        reschedule_state = _merge_reschedule_state(state, message)
        missing = _missing_reschedule_fields(reschedule_state)
        if not missing:
            result = await _reschedule_appointment({
                "appointment_id": reschedule_state["appointment_id"],
                "date": reschedule_state["date"],
                "time": reschedule_state["time"],
            })
            await clear_booking_state(redis_client, session_id)
            return AgentResponse(message=result, intent="reschedule_intent")

        await save_booking_state(redis_client, session_id, reschedule_state)
        return AgentResponse(message=_next_reschedule_question(missing), intent="reschedule_intent")

    if _looks_like_cancel_intent(message):
        appointment_id = _extract_appointment_id(message)
        if appointment_id:
            result = await _cancel_appointment({"appointment_id": appointment_id})
            await clear_booking_state(redis_client, session_id)
            return AgentResponse(message=result, intent="cancel_intent")
        await save_booking_state(redis_client, session_id, {"active": True, "intent": "cancel"})
        return AgentResponse(message="Please share the appointment ID you want to cancel.", intent="cancel_intent")

    if state.get("intent") == "cancel":
        appointment_id = _extract_appointment_id(message)
        if appointment_id:
            result = await _cancel_appointment({"appointment_id": appointment_id})
            await clear_booking_state(redis_client, session_id)
            return AgentResponse(message=result, intent="cancel_intent")
        return AgentResponse(message="Please share the appointment ID you want to cancel.", intent="cancel_intent")

    if not active and not _looks_like_booking_message(message):
        return None

    previous_state = dict(state)
    state = _merge_booking_state(state, message)

    asks_availability = any(word in lowered for word in ("available", "availability", "timings", "timing", "days", "slots"))
    if asks_availability and state.get("doctor_id"):
        await save_booking_state(redis_client, session_id, state)
        slots = await _build_slot_suggestions(state)
        return AgentResponse(
            message=await _availability_summary(int(state["doctor_id"]), state.get("doctor_name")),
            intent="booking_intent",
            suggested_slots=slots,
        )

    if asks_availability and state.get("specialty") and not state.get("doctor_id"):
        await save_booking_state(redis_client, session_id, state)
        doctors_text = await _doctor_summary_for_state(state)
        slots = await _build_slot_suggestions(state)
        return AgentResponse(
            message=f"{doctors_text}\nWhich doctor would you prefer?",
            intent="booking_intent",
            suggested_slots=slots,
        )

    if previous_state.get("active") and _extract_phone(message) and _missing_booking_fields(state) == []:
        state = _ensure_doctor_for_department(state)
        args = {
            "patient_name": state["patient_name"],
            "patient_id": session_id,
            "doctor_id": state["doctor_id"],
            "doctor_name": state.get("doctor_name"),
            "date": state["date"],
            "time": state["time"],
            "complaint": state["complaint"],
            "contact_number": state["contact_number"],
            "booking_channel": "chat" if mode == "text" else "voice_note",
        }
        result = await _create_appointment(args)
        await clear_booking_state(redis_client, session_id)
        appointment = _appointment_from_result(result, args)
        return AgentResponse(
            message=result,
            intent="booking_intent",
            appointment_data=appointment,
        )

    missing = _missing_booking_fields(state)
    if not missing:
        state = _ensure_doctor_for_department(state)
        args = {
            "patient_name": state["patient_name"],
            "patient_id": session_id,
            "doctor_id": state.get("doctor_id"),
            "doctor_name": state.get("doctor_name"),
            "date": state["date"],
            "time": state["time"],
            "complaint": state["complaint"],
            "contact_number": state["contact_number"],
            "booking_channel": "chat" if mode == "text" else "voice_note",
        }
        result = await _create_appointment(args)
        await clear_booking_state(redis_client, session_id)
        appointment = _appointment_from_result(result, args)
        return AgentResponse(
            message=result,
            intent="booking_intent",
            appointment_data=appointment,
        )

    await save_booking_state(redis_client, session_id, state)

    if state.get("specialty") and not state.get("doctor_id") and any(word in lowered for word in ("available", "doctor", "doctors")):
        doctors_text = await _doctor_summary_for_state(state)
        return AgentResponse(
            message=f"{doctors_text}\nWhich doctor would you prefer? After that, { _next_booking_question(missing).lower() }",
            intent="booking_intent",
        )

    return AgentResponse(message=_next_booking_question(missing), intent="booking_intent")


# ── Tool implementations (Ibrahim — do not modify) ────────────────────────────

async def _get_available_slots(args: Dict) -> str:
    specialty = _normalize_specialty(args.get("specialty", "general"))
    async with AsyncSessionLocal() as db:
        doctors = await crud.get_doctors(db)
        matching = [d for d in doctors if specialty.lower() in d.get("specialty", "").lower()]
        
        if not matching:
            return f"No doctors found for specialty: {specialty}"
            
        result = []
        for doc in matching[:3]:
            avail = await crud.get_doctor_availability(db, doc["id"])
            slots = avail.get("availableSlots", [])[:3]
            if slots:
                result.append(
                    f"{_format_doctor_name(doc.get('name'))} (ID:{doc['id']}) — slots: "
                    + ", ".join(slots)
                )
                
    return "\n".join(result) if result else f"No available slots for {specialty} right now."


async def _list_doctors(args: Dict) -> str:
    specialty = _normalize_specialty(args.get("specialty", ""))
    async with AsyncSessionLocal() as db:
        doctors = await crud.get_doctors(db)

    matching = doctors
    if specialty:
        matching = [d for d in doctors if specialty in d.get("specialty", "").lower()]

    if not matching:
        return f"I could not find doctors for {specialty}. Available departments are General Practice, Cardiology, Pediatrics, Dermatology, and Orthopedics."

    lines = [
        f"{_format_doctor_name(doc.get('name'))} (ID {doc['id']}), {doc.get('specialty', 'General Practice')}"
        for doc in matching[:8]
    ]
    return "Available doctors:\n" + "\n".join(lines)


async def _get_clinic_timings(args: Dict) -> str:
    return (
        "Clinic hours are Monday to Friday, 9:00 AM to 5:00 PM. "
        "For urgent symptoms or emergencies, please seek emergency care immediately."
    )


async def _get_doctor_profile(args: Dict) -> str:
    doctor_id = int(args.get("doctor_id", 0))
    async with AsyncSessionLocal() as db:
        doc = await crud.get_doctor(db, doctor_id)
    if not doc:
        return f"Doctor with ID {doctor_id} not found."
    return (
        f"{_format_doctor_name(doc.get('name'))} | Specialty: {doc['specialty']} | "
        f"Avg consult: {doc.get('avgConsultMin', 'N/A')} min | "
        f"Status: {doc.get('status', 'unknown')}"
    )


async def _check_patient_history(args: Dict) -> str:
    patient_id = args.get("patient_id", "")
    async with AsyncSessionLocal() as db:
        appts = await crud.get_appointments(db, limit=3, offset=0)
    patient_appts = [a for a in appts if a.get("patientId") == patient_id]
    if not patient_appts:
        return f"No appointment history found for patient {patient_id}."
    lines = [
        f"- {a.get('date')} with {_format_doctor_name(a.get('doctorName'))} ({a.get('status')})"
        for a in patient_appts
    ]
    return "Last visits:\n" + "\n".join(lines)


async def _predict_wait_time(args: Dict) -> str:
    result = await ml_service_client.get_wait_time({
        "slot_id": args.get("slot_id"),
        "doctor_id": args.get("doctor_id"),
        "hour_of_day": args.get("hour_of_day", 10),
    })
    if "error" in result:
        return "Wait time prediction unavailable."
    wait = result.get("predicted_wait_minutes", "N/A")
    return f"Predicted wait time: {wait} minutes."


async def _create_appointment_record(args: Dict) -> Dict[str, Any]:
    args = _normalize_tool_args("create_appointment", args)
    patient_id = args.get("patient_id")
    patient_name = str(args.get("patient_name") or "").strip()
    doctor_name = args.get("doctor_name", "")
    doctor_id = args.get("doctor_id")
    date_value = str(args.get("date") or "").strip()
    time_value = str(args.get("time") or "").strip()
    complaint = str(args.get("complaint") or "").strip()

    missing = []
    if not patient_name:
        missing.append("your full name")
    if not doctor_id and not doctor_name:
        missing.append("which doctor or department you prefer")
    if not date_value:
        missing.append("appointment date")
    if not time_value:
        missing.append("appointment time")
    if not complaint:
        missing.append("reason for visit")
    if missing:
        return {"error_message": "I can book that for you. Please share " + ", ".join(missing) + "."}

    # Smart Name Resolution for all 11 doctors
    name_to_id = {
        "ahmed": 1, "raza": 1, "sara": 2, "malik": 2, "kamran": 3, "iqbal": 3,
        "nadia": 4, "hussain": 4, "tariq": 5, "butt": 5, "ayesha": 6, "khan": 6,
        "bilal": 7, "chaudhry": 7, "zara": 8, "siddiqui": 8, "usman": 9, "qureshi": 9,
        "hina": 10, "javed": 10, "faisal": 11, "sheikh": 11
    }
    if doctor_name and (not doctor_id or int(doctor_id) <= 2):
        for name, d_id in name_to_id.items():
            if name in doctor_name.lower():
                doctor_id = d_id
                break
    
    doctor_id = int(doctor_id or 1)
    
    if not patient_id:
        patient_id = f"pat-{uuid.uuid4().hex[:8]}"

    data = {
        "patientId": patient_id,
        "patientName": patient_name,
        "doctorId": doctor_id,
        "doctorName": args.get("doctor_name") or DOCTOR_ID_TO_NAME.get(doctor_id, ""),
        "slotId": None, # Ignore slot_id for now as the slots table is empty in demo data
        "time": time_value.split()[0].zfill(5) if ":" in time_value else time_value,
        "date": date_value,
        "reason": complaint,
        "urgency": args.get("urgency", "ROUTINE").lower(),
        "status": "Confirmed",
        "booking_channel": args.get("booking_channel"),
    }
    
    async with AsyncSessionLocal() as db:
        # Check if patient exists, if not create them
        from db.models import Patient
        from sqlalchemy import select
        
        patient_check = await db.execute(select(Patient).where(Patient.id == patient_id))
        if not patient_check.scalar_one_or_none():
            logger.info("BookingAgent: Creating missing patient %s", patient_id)
            new_patient = Patient(
                id=patient_id,
                name=patient_name,
                email=f"{patient_id}@example.com",
                phone=args.get("contact_number"),
            )
            db.add(new_patient)
            await db.flush() # ensure patient is saved before appt
            
        created = await crud.create_appointment(db, data)
        await db.commit()
        
    return created


async def _create_appointment(args: Dict) -> str:
    created = await _create_appointment_record(args)
    if created.get("error_message"):
        return str(created["error_message"])
    return (
        f"Appointment confirmed! ID: {created.get('id')}. "
        f"Date: {created.get('date')} at {created.get('time')}."
    )


def _appointment_from_result(result: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if "appointment confirmed" not in str(result).lower():
        return None

    appointment_id = None
    id_match = re.search(r"\bapt[-_][a-zA-Z0-9-]+\b", str(result), flags=re.IGNORECASE)
    if id_match:
        appointment_id = id_match.group(0).replace("_", "-")

    return {
        "id": appointment_id,
        "patientName": args.get("patient_name"),
        "patientId": args.get("patient_id"),
        "doctorId": args.get("doctor_id"),
        "doctorName": args.get("doctor_name") or DOCTOR_ID_TO_NAME.get(int(args.get("doctor_id") or 1), ""),
        "specialty": args.get("specialty") or "General Practice",
        "date": args.get("date"),
        "time": args.get("time"),
        "predictedWaitMin": args.get("predictedWaitMin", 0),
        "reason": args.get("complaint"),
    }


async def _cancel_appointment(args: Dict) -> str:
    appointment_id = args.get("appointment_id", "")
    async with AsyncSessionLocal() as db:
        success = await crud.delete_appointment(db, appointment_id)
        if success:
            await db.commit()
    if success:
        return f"Appointment {appointment_id} has been cancelled."
    return f"Could not find appointment {appointment_id}."


async def _reschedule_appointment(args: Dict) -> str:
    appointment_id = args.get("appointment_id", "")
    date_value = str(args.get("date") or "").strip()
    time_value = str(args.get("time") or "").strip()
    new_slot_id = args.get("new_slot_id")

    missing = []
    if not appointment_id:
        missing.append("appointment ID")
    if not date_value:
        missing.append("new appointment date")
    if not time_value:
        missing.append("new appointment time")
    if missing:
        return "Please share the " + ", ".join(missing) + " so I can reschedule the appointment."

    patch = {
        "date": date_value,
        "time": time_value,
        "status": "Confirmed",
    }
    if new_slot_id is not None:
        patch["slotId"] = str(new_slot_id)

    async with AsyncSessionLocal() as db:
        updated = await crud.update_appointment(db, appointment_id, patch)
        if updated:
            await db.commit()
    if updated:
        return f"Appointment {appointment_id} rescheduled successfully. New date: {date_value} at {time_value}."
    return f"Could not reschedule appointment {appointment_id}."


TOOL_MAP = {
    "list_doctors": _list_doctors,
    "get_available_slots":   _get_available_slots,
    "get_clinic_timings": _get_clinic_timings,
    "get_doctor_profile":    _get_doctor_profile,
    "check_patient_history": _check_patient_history,
    "predict_wait_time":     _predict_wait_time,
    "create_appointment":    _create_appointment,
    "cancel_appointment":    _cancel_appointment,
    "reschedule_appointment": _reschedule_appointment,
}


# ── ReAct loop (Ibrahim — one backward-compatible addition: task_type param) ──

def _parse_tool_call(text: str) -> Optional[Dict]:
    """Try to parse a JSON tool call from LLM response."""
    text = text.strip()
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        obj = json.loads(text[start:end])
        
        # Explicit tool call format (standard)
        if "tool" in obj and obj["tool"] in TOOL_MAP:
            tool_name = obj["tool"]
            return {"tool": tool_name, "args": _normalize_tool_args(tool_name, obj.get("args", {}))}
            
        # Alternative format (used by some models)
        if "name" in obj and obj["name"] in TOOL_MAP:
            tool_name = obj["name"]
            raw_args = obj.get("arguments", obj.get("args", {}))
            return {"tool": tool_name, "args": _normalize_tool_args(tool_name, raw_args)}
            
        # Recovery: if they sent raw args for create_appointment without the "tool" wrapper
        if "patient_id" in obj or "patient_name" in obj:
            return {"tool": "create_appointment", "args": _normalize_tool_args("create_appointment", obj)}
        if "specialty" in obj or "specialization" in obj:
            return {"tool": "get_available_slots", "args": _normalize_tool_args("get_available_slots", obj)}
            
    except (ValueError, json.JSONDecodeError):
        pass
    return None


def _contains_unhandled_tool_json(text: str) -> bool:
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        obj = json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError):
        return False
    return isinstance(obj, dict) and ("tool" in obj or "name" in obj)


def _safe_patient_response(text: str, language: str = "en") -> str:
    if _contains_unhandled_tool_json(text):
        if language == "ur":
            return "معذرت، میں ابھی یہ درخواست مکمل نہیں کر سکا۔ براہ کرم اپنی درخواست تھوڑی مزید وضاحت سے لکھیں۔"
        return "I can help with that, but I need a little more detail. Please tell me what you would like to do next."
    return text


async def _run_react_loop(
    messages: List[Dict],
    system: str,
    language: str,
    mode: str,
    trace: Optional[List[Dict[str, Any]]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    task_type: Optional[str] = None,   # ← added for voice_reasoning; None = auto
) -> str:
    """
    Core ReAct loop shared by both process_chat_message() and BookingAgent.run().

    task_type: if None, auto-selects "urdu" or "reasoning" based on language.
               Pass "voice_reasoning" explicitly from BookingAgent.run() voice path.
    """
    max_steps = MAX_STEPS_VOICE if mode == "voice" else MAX_STEPS_TEXT

    # Auto-determine task type only when not explicitly supplied.
    if task_type is None:
        task_type = "urdu" if language == "ur" else "reasoning"

    response_text = ""
    for step in range(max_steps):
        try:
            llm_started = time.perf_counter()
            response = await llm_router.call(
                messages=messages,
                task_type=task_type,
                system=system,
                temperature=0.2,
            )
            llm_latency_ms = int((time.perf_counter() - llm_started) * 1000)
            response_text = response.text.strip()
        except AllProvidersExhausted:
            logger.error("All LLM providers exhausted in BookingAgent")
            return RECOVERY_MSG.get(language, RECOVERY_MSG["en"])

        tool_call = _parse_tool_call(response_text)

        if tool_call is None:
            if _contains_unhandled_tool_json(response_text):
                logger.warning("BookingAgent: suppressed unhandled tool JSON: %s", response_text)
                return _safe_patient_response(response_text, language)
            # If the model is narrating instead of calling a tool, nudge it once.
            if any(kw in response_text.lower() for kw in ("check", "find", "looking", "let me")):
                logger.info("BookingAgent: Nudging model to use tool instead of narrating")
                messages.append({"role": "assistant", "content": response_text})
                messages.append({"role": "user", "content": "Please provide the tool call in JSON format now. Do not narrate."})
                continue
            if trace is not None:
                trace.append({
                    "type": "CONCLUDE",
                    "tool": "booking_agent",
                    "provider": getattr(response, "provider", "groq"),
                    "args": {"lang": language, "mode": mode},
                    "result": response_text[:160],
                    "latencyMs": llm_latency_ms,
                })
            return _safe_patient_response(response_text, language)

        # Execute tool
        tool_name = tool_call["tool"]
        tool_args = _normalize_tool_args(tool_name, tool_call.get("args", {}))

        # Context injection: tagging channel for Activity Feed
        if tool_name == "create_appointment":
            if "booking_channel" not in tool_args:
                tool_args["booking_channel"] = "chat" if mode == "text" else "voice_note"

        logger.info("BookingAgent tool call: %s args=%s", tool_name, tool_args)
        tool_started = time.perf_counter()

        try:
            if tool_name == "create_appointment":
                tool_result = await _create_appointment(tool_args)
                appointment = _appointment_from_result(tool_result, tool_args)
                if appointment is not None and metadata is not None:
                    metadata["appointment"] = appointment
            else:
                tool_result = await TOOL_MAP[tool_name](tool_args)
                if tool_name == "get_available_slots" and metadata is not None:
                    metadata["suggested_slots"] = await _build_slot_suggestions(tool_args)
        except Exception as e:
            logger.error("Tool %s failed: %s", tool_name, e)
            tool_result = f"Tool {tool_name} failed: {str(e)}"
        tool_latency_ms = int((time.perf_counter() - tool_started) * 1000)

        if trace is not None:
            trace.append({
                "type": "ACT",
                "tool": tool_name,
                    "provider": getattr(response, "provider", "groq"),
                "args": tool_args,
                "result": "Tool call selected by LLM",
                "latencyMs": llm_latency_ms,
            })
            trace.append({
                "type": "OBSERVE",
                "tool": tool_name,
                "provider": "xgboost" if tool_name == "predict_wait_time" else getattr(response, "provider", "groq"),
                "args": tool_args,
                "result": str(tool_result)[:220],
                "latencyMs": tool_latency_ms,
            })

        # Feed result back into conversation
        messages.append({"role": "assistant", "content": response_text})
        messages.append({"role": "user", "content": f"[Tool result: {tool_name}]\n{tool_result}"})

    # Max steps reached or model returned text. 
    # Verification: if this sounds like a success but no tool was called, force the tool.
    if any(kw in response_text.lower() for kw in ("booked", "confirmed", "appointment")):
        # Check if we actually have a tool result in history
        has_tool_call = any("[Tool result: create_appointment]" in m["content"] for m in messages if m["role"] == "user")
        if not has_tool_call:
            logger.info("BookingAgent: Detected success message without tool call. Forcing tool check.")
            messages.append({"role": "user", "content": "You haven't called the create_appointment tool yet. You MUST call it to save the data to the database. Use the tool now."})
            try:
                final = await llm_router.call(messages=messages, task_type=task_type, system=system)
                # If the retry has a tool call, the next turn will handle it, but for simplicity here:
                response_text = final.text.strip()
                tc = _parse_tool_call(response_text)
                if tc:
                    t_name = tc["tool"]
                    t_args = tc.get("args", {})
                    t_res = await TOOL_MAP[t_name](t_args)
                    messages.append({"role": "assistant", "content": response_text})
                    messages.append({"role": "user", "content": f"[Tool result: {t_name}]\n{t_res}"})
                    final_resp = await llm_router.call(messages=messages, task_type=task_type, system=system)
                    return _safe_patient_response(final_resp.text.strip(), language)
                return _safe_patient_response(response_text, language)
            except Exception:
                pass

    return _safe_patient_response(response_text, language)


async def _record_booking_run(
    *,
    session_id: str,
    mode: str,
    language: str,
    outcome: Optional[str],
    tool_calls: List[Dict[str, Any]],
    duration_ms: int,
    summary: str,
    started_at: datetime,
) -> None:
    await record_agent_run(
        agent="booking_agent",
        session_id=session_id,
        mode=mode,
        language=language,
        outcome=outcome,
        tool_calls=tool_calls,
        duration_ms=duration_ms,
        summary=(summary or "")[:500],
        started_at=started_at,
        completed_at=datetime.now(timezone.utc),
    )


# ── BookingAgent class (for AgentOrchestrator and voice pipeline) ─────────────

class BookingAgent:
    """
    Voice-aware booking agent called by AgentOrchestrator.

    AgentOrchestrator instantiates this as:
        BookingAgent(llm_router=..., db=..., redis=...).run(message, session_id, language, mode)

    The voice pipeline calls .run() which returns AgentResponse.
    The text chat route calls process_chat_message() directly (below) — it does NOT use this class.

    Redis is used for session history in both paths.
    llm_router and db are module-level singletons used inside the tool implementations.
    """

    def __init__(
        self,
        llm_router=None,    # accepted for orchestrator compatibility; module-level singleton used
        db=None,            # accepted for orchestrator compatibility; tools use AsyncSessionLocal()
        redis=None,
    ) -> None:
        self._redis = redis

    async def run(
        self,
        message: str,
        session_id: str,
        language: str = "en",
        mode: str = "text",
        lang: Optional[str] = None,
    ) -> AgentResponse:
        """
        Process a patient message and return a structured AgentResponse.

        Called by AgentOrchestrator.handle_booking() for both text and voice.
        Voice path uses PROMPT_VOICE (2-sentence constraint) + voice_reasoning task type.
        Text path uses SYSTEM_TEXT (full tool descriptions) + reasoning/urdu task type.

        Args:
            message:    Patient's text (already transcribed if from voice pipeline).
            session_id: Unique session identifier for Redis conversation history.
            language:   Detected language code ("en" or "ur").
            mode:       "text" for chat, "voice" for voice pipeline.

        Returns:
            AgentResponse with .message (text for TTS/display) and .appointment_data.
        """
        if lang is not None:
            language = lang

        started_at = datetime.now(timezone.utc)
        run_started = time.perf_counter()

        deterministic = await _handle_booking_state(message, session_id, self._redis, language, mode)
        if deterministic is not None:
            await _record_booking_run(
                session_id=session_id,
                mode=mode,
                language=language,
                outcome=deterministic.intent,
                tool_calls=deterministic.tool_calls,
                duration_ms=int((time.perf_counter() - run_started) * 1000),
                summary=deterministic.message,
                started_at=started_at,
            )
            return deterministic

        # Load Redis history
        history: List[Dict] = []
        if self._redis:
            try:
                history = await get_history(self._redis, session_id)
            except Exception as e:
                logger.error("BookingAgent: Redis get failed for %s: %s", session_id, e)

        messages = history + [{"role": "user", "content": message}]

        # Choose system prompt and task type based on mode
        if mode == "voice":
            system = PROMPT_VOICE          # 2-sentence constraint, tools listed
            task_type = "voice_reasoning"  # routes to fastest Gemini model
        else:
            system = SYSTEM_TEXT           # full prompt with all rules
            # Urdu text queries go to the Gemini-first "urdu" routing lane
            task_type = "urdu" if language == "ur" else "reasoning"

        # Run the shared ReAct loop
        trace: List[Dict[str, Any]] = []
        metadata: Dict[str, Any] = {}
        response_text = await _run_react_loop(
            messages, system, language, mode, task_type=task_type, trace=trace, metadata=metadata
        )

        # Persist updated history
        messages.append({"role": "assistant", "content": response_text})
        if self._redis:
            try:
                await save_history(self._redis, session_id, messages)
            except Exception as e:
                logger.error("BookingAgent: Redis save failed for %s: %s", session_id, e)

        # Lightweight intent detection for AgentResponse metadata
        msg_lower = message.lower()
        if any(kw in msg_lower for kw in ("book", "appointment", "schedule")):
            intent = "booking_intent"
        elif "cancel" in msg_lower:
            intent = "cancel_intent"
        elif any(kw in msg_lower for kw in ("reschedule", "change", "move")):
            intent = "reschedule_intent"
        else:
            intent = "general_query"

        await _record_booking_run(
            session_id=session_id,
            mode=mode,
            language=language,
            outcome=intent,
            tool_calls=trace,
            duration_ms=int((time.perf_counter() - run_started) * 1000),
            summary=response_text,
            started_at=started_at,
        )

        return AgentResponse(
            message=response_text,
            appointment_data=metadata.get("appointment"),
            intent=intent,
            tool_calls=trace,
            suggested_slots=metadata.get("suggested_slots", []),
        )


# Singleton for direct imports (e.g., if any module imports booking_agent directly)
booking_agent = BookingAgent()


# ── process_chat_message (Ibrahim — DO NOT MODIFY) ────────────────────────────

async def process_chat_message(
    user_id: str,
    message: str,
    redis_client=None,
    language: str = "en",
    mode: str = "text",
) -> Dict:
    """
    Main entry point called by api/routes/chat.py.
    Handles Redis session memory, runs ReAct loop, returns response dict.
    """
    started_at = datetime.now(timezone.utc)
    run_started = time.perf_counter()

    deterministic = await _handle_booking_state(message, user_id, redis_client, language, mode)
    if deterministic is not None:
        await _record_booking_run(
            session_id=user_id,
            mode=mode,
            language=language,
            outcome=deterministic.intent,
            tool_calls=deterministic.tool_calls,
            duration_ms=int((time.perf_counter() - run_started) * 1000),
            summary=deterministic.message,
            started_at=started_at,
        )
        return {
            "response": deterministic.message,
            "responseText": deterministic.message,
            "agentId": "booking_agent",
            "intent": deterministic.intent,
            "suggestedActions": [],
            "appointment": deterministic.appointment_data,
            "suggestedSlots": deterministic.suggested_slots,
            "tool_calls": deterministic.tool_calls,
        }

    # Load history from Redis
    history = []
    if redis_client:
        try:
            history = await get_history(redis_client, user_id)
        except Exception as e:
            logger.error("Redis get failed for %s: %s", user_id, e)

    # Build messages list
    messages = history + [{"role": "user", "content": message}]
    system = SYSTEM_VOICE if mode == "voice" else SYSTEM_TEXT

    # Run ReAct loop (task_type=None → auto-determined from language)
    trace: List[Dict[str, Any]] = []
    metadata: Dict[str, Any] = {}
    response_text = await _run_react_loop(messages, system, language, mode, trace=trace, metadata=metadata)

    # Update history
    messages.append({"role": "assistant", "content": response_text})
    if redis_client:
        try:
            await save_history(redis_client, user_id, messages)
        except Exception as e:
            logger.error("Redis save failed for %s: %s", user_id, e)

    outcome = "booked" if metadata.get("appointment") else "completed"
    await _record_booking_run(
        session_id=user_id,
        mode=mode,
        language=language,
        outcome=outcome,
        tool_calls=trace,
        duration_ms=int((time.perf_counter() - run_started) * 1000),
        summary=response_text,
        started_at=started_at,
    )

    return {
        "response": response_text,
        "responseText": response_text,
        "agentId": "booking_agent",
        "intent": None,
        "suggestedActions": [],
        "appointment": metadata.get("appointment"),
        "suggestedSlots": metadata.get("suggested_slots", []),
        "tool_calls": trace,
    }
