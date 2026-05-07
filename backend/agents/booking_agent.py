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
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from db.session import AsyncSessionLocal
from db import crud
from services.llm_router import llm_router, AllProvidersExhausted
from services.redis_memory import get_history, save_history, RECOVERY_MSG
from services.ml_service import ml_service_client

logger = logging.getLogger(__name__)

MAX_STEPS_TEXT = 5
MAX_STEPS_VOICE = 3

# ── System prompts ────────────────────────────────────────────────────────────

SYSTEM_TEXT = """You are MediFlow, a bilingual (English and Urdu) AI clinic assistant.
You help patients book, reschedule, and cancel appointments.

You have access to the following tools. To use a tool, respond with ONLY a JSON object:
{"tool": "<tool_name>", "args": {<arguments>}}

Available tools:
- get_available_slots: {"specialty": str, "date": "YYYY-MM-DD" (optional)}
- get_doctor_profile: {"doctor_id": int}
- check_patient_history: {"patient_id": str}
- predict_wait_time: {"slot_id": int, "doctor_id": int, "hour_of_day": int}
- create_appointment: {"patient_id": str, "slot_id": int, "doctor_id": int, "complaint": str, "urgency": "ROUTINE"|"MODERATE"|"URGENT"}
- cancel_appointment: {"appointment_id": str}
- reschedule_appointment: {"appointment_id": str, "new_slot_id": int}

Rules:
- If you need information to answer, use a tool first.
- Only call create_appointment after the patient explicitly confirms.
- If the patient writes in Urdu, respond in Urdu.
- When done, respond with plain text (no JSON).
- Be concise and friendly.
"""

SYSTEM_VOICE = """You are MediFlow, a bilingual clinic assistant on a voice call.
Keep all responses to 1-2 short sentences maximum.
Use tools by responding with JSON: {"tool": "<name>", "args": {}}
When done, respond with plain text only. If patient speaks Urdu, reply in Urdu.

Tools: get_available_slots, get_doctor_profile, predict_wait_time,
       create_appointment, cancel_appointment, reschedule_appointment
"""


# ── Tool implementations ──────────────────────────────────────────────────────

async def _get_available_slots(args: Dict) -> str:
    specialty = args.get("specialty", "general")
    async with AsyncSessionLocal() as db:
        doctors = await crud.get_doctors(db)
    matching = [d for d in doctors if specialty.lower() in d.get("specialty", "").lower()]
    if not matching:
        return f"No doctors found for specialty: {specialty}"
    result = []
    for doc in matching[:3]:
        async with AsyncSessionLocal() as db:
            avail = await crud.get_doctor_availability(db, doc["id"])
        slots = avail.get("slots", [])[:3]
        if slots:
            result.append(f"Dr. {doc['name']} (ID:{doc['id']}) — slots: " +
                         ", ".join(str(s.get("start_time", "")) for s in slots))
    return "\n".join(result) if result else f"No available slots for {specialty} right now."


async def _get_doctor_profile(args: Dict) -> str:
    doctor_id = int(args.get("doctor_id", 0))
    async with AsyncSessionLocal() as db:
        doc = await crud.get_doctor(db, doctor_id)
    if not doc:
        return f"Doctor with ID {doctor_id} not found."
    return (f"Dr. {doc['name']} | Specialty: {doc['specialty']} | "
            f"Avg consult: {doc.get('avgConsultMin', 'N/A')} min | "
            f"Status: {doc.get('status', 'unknown')}")


async def _check_patient_history(args: Dict) -> str:
    patient_id = args.get("patient_id", "")
    async with AsyncSessionLocal() as db:
        appts = await crud.get_appointments(db, limit=3, offset=0)
    patient_appts = [a for a in appts if a.get("patientId") == patient_id]
    if not patient_appts:
        return f"No appointment history found for patient {patient_id}."
    lines = [f"- {a.get('date')} with Dr. {a.get('doctorName')} ({a.get('status')})"
             for a in patient_appts]
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


async def _create_appointment(args: Dict) -> str:
    data = {
        "patientId": args.get("patient_id", f"pat-{uuid.uuid4().hex[:8]}"),
        "patientName": args.get("patient_name", "Patient"),
        "doctorId": str(args.get("doctor_id")),
        "doctorName": args.get("doctor_name", ""),
        "slotId": str(args.get("slot_id")),
        "time": args.get("time", "09:00"),
        "date": args.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
        "reason": args.get("complaint", "General consultation"),
        "urgency": args.get("urgency", "ROUTINE").lower(),
        "status": "Confirmed",
    }
    async with AsyncSessionLocal() as db:
        created = await crud.create_appointment(db, data)
    return f"Appointment confirmed! ID: {created.get('id')}. Date: {data['date']} at {data['time']}."


async def _cancel_appointment(args: Dict) -> str:
    appointment_id = args.get("appointment_id", "")
    async with AsyncSessionLocal() as db:
        success = await crud.delete_appointment(db, appointment_id)
    if success:
        return f"Appointment {appointment_id} has been cancelled."
    return f"Could not find appointment {appointment_id}."


async def _reschedule_appointment(args: Dict) -> str:
    appointment_id = args.get("appointment_id", "")
    new_slot_id = args.get("new_slot_id")
    async with AsyncSessionLocal() as db:
        updated = await crud.update_appointment(db, appointment_id, {
            "slotId": str(new_slot_id),
            "status": "Confirmed",
        })
    if updated:
        return f"Appointment {appointment_id} rescheduled successfully."
    return f"Could not reschedule appointment {appointment_id}."


TOOL_MAP = {
    "get_available_slots": _get_available_slots,
    "get_doctor_profile": _get_doctor_profile,
    "check_patient_history": _check_patient_history,
    "predict_wait_time": _predict_wait_time,
    "create_appointment": _create_appointment,
    "cancel_appointment": _cancel_appointment,
    "reschedule_appointment": _reschedule_appointment,
}


# ── ReAct loop ────────────────────────────────────────────────────────────────

def _parse_tool_call(text: str) -> Optional[Dict]:
    """Try to parse a JSON tool call from LLM response."""
    text = text.strip()
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        obj = json.loads(text[start:end])
        if "tool" in obj and obj["tool"] in TOOL_MAP:
            return obj
    except (ValueError, json.JSONDecodeError):
        pass
    return None


async def _run_react_loop(
    messages: List[Dict],
    system: str,
    language: str,
    mode: str,
) -> str:
    max_steps = MAX_STEPS_VOICE if mode == "voice" else MAX_STEPS_TEXT
    task_type = "urdu" if language == "ur" else "reasoning"

    for step in range(max_steps):
        try:
            response = await llm_router.call(
                messages=messages,
                task_type=task_type,
                system=system,
                temperature=0.2,
            )
        except AllProvidersExhausted:
            logger.error("All LLM providers exhausted in BookingAgent")
            return RECOVERY_MSG.get(language, RECOVERY_MSG["en"])

        text = response.text.strip()
        tool_call = _parse_tool_call(text)

        if tool_call is None:
            # Plain text response — done
            return text

        # Execute tool
        tool_name = tool_call["tool"]
        tool_args = tool_call.get("args", {})
        logger.info("BookingAgent tool call: %s args=%s", tool_name, tool_args)

        try:
            tool_result = await TOOL_MAP[tool_name](tool_args)
        except Exception as e:
            logger.error("Tool %s failed: %s", tool_name, e)
            tool_result = f"Tool {tool_name} failed: {str(e)}"

        # Feed result back into conversation
        messages.append({"role": "assistant", "content": text})
        messages.append({"role": "user", "content": f"[Tool result: {tool_name}]\n{tool_result}"})

    # Max steps reached — ask LLM to wrap up
    messages.append({"role": "user", "content": "Please give your final response now."})
    try:
        final = await llm_router.call(
            messages=messages,
            task_type=task_type,
            system=system,
            temperature=0.2,
        )
        return final.text.strip()
    except AllProvidersExhausted:
        return RECOVERY_MSG.get(language, RECOVERY_MSG["en"])


# ── Main entry point ──────────────────────────────────────────────────────────

async def process_chat_message(
    user_id: str,
    message: str,
    redis_client=None,
    language: str = "en",
    mode: str = "text",
) -> Dict:
    """
    Main entry point called by chat.py route.
    Handles Redis session memory, runs ReAct loop, returns response dict.
    """
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

    # Run ReAct loop
    response_text = await _run_react_loop(messages, system, language, mode)

    # Update history
    messages.append({"role": "assistant", "content": response_text})
    if redis_client:
        try:
            await save_history(redis_client, user_id, messages)
        except Exception as e:
            logger.error("Redis save failed for %s: %s", user_id, e)

    return {
        "response": response_text,
        "agentId": "booking_agent",
        "intent": None,
        "suggestedActions": [],
    }