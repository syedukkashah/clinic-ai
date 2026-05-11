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
import uuid
from dataclasses import dataclass, field
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


# ── System prompts ────────────────────────────────────────────────────────────

SYSTEM_TEXT = """You are MediFlow, the official AI Booking Agent for the clinic. 
You have DIRECT ACCESS to the clinic's database through tools. 

### YOUR CLINIC KNOWLEDGE (Doctor IDs):
- **General Practice**: Dr. Ahmed Raza (1), Dr. Sara Malik (2), Dr. Kamran Iqbal (3)
- **Cardiology**: Dr. Nadia Hussain (4), Dr. Tariq Butt (5)
- **Pediatrics**: Dr. Ayesha Khan (6), Dr. Bilal Chaudhry (7)
- **Dermatology**: Dr. Zara Siddiqui (8), Dr. Usman Qureshi (9)
- **Orthopedics**: Dr. Hina Javed (10), Dr. Faisal Sheikh (11)` 

### HOW TO OPERATE:
1. **TOOL FORMAT**: You MUST respond with a JSON object in this EXACT format:
   `{"tool": "tool_name", "args": {"param": "value"}}`
2. **NO NARRATION**: Go DIRECTLY to the tool call.
3. **MANDATORY**: NEVER tell the patient to "contact the website" or "call reception".
4. **FINAL RESPONSE**: Only provide plain text confirmation AFTER you have called `create_appointment`.
"""

# Voice prompt: same tool list as SYSTEM_TEXT but with the 2-sentence constraint
# enforced to keep TTS synthesis under 1.2s (part of the 4-8s voice latency budget).
PROMPT_VOICE = """You are MediFlow, the clinic's voice assistant. 
You handle live calls to book appointments. You have direct database tools.

### YOUR CLINIC KNOWLEDGE (Doctor IDs):
- **General**: Dr. Ahmed Raza (1), Dr. Sara Malik (2), Dr. Kamran Iqbal (3)
- **Cardiology**: Dr. Nadia Hussain (4), Dr. Tariq Butt (5)
- **Pediatrics**: Dr. Ayesha Khan (6), Dr. Bilal Chaudhry (7)
- **Dermatology**: Dr. Zara Siddiqui (8), Dr. Usman Qureshi (9)
- **Orthopedics**: Dr. Hina Javed (10), Dr. Faisal Sheikh (11)

### VOICE CONSTRAINTS:
- Keep conversational responses to MAX 2 SENTENCES.
- No markdown, no asterisks, no bullet points. Plain spoken text only.
- NEVER say "I will check" or "Let me find that". Just use the tool.
- If the caller speaks Urdu, reply in Urdu.

### TOOLS:
- get_available_slots: {"tool": "get_available_slots", "args": {"specialty": "general"}}
- get_doctor_profile: {"tool": "get_doctor_profile", "args": {"doctor_id": 1}}
- create_appointment: {"tool": "create_appointment", "args": {"patient_id": "...", "patient_name": "...", "doctor_id": 1, "complaint": "...", "urgency": "ROUTINE", "time": "14:30"}}
- cancel_appointment: {"tool": "cancel_appointment", "args": {"appointment_id": "..."}}
"""

# Alias kept for any code that still imports SYSTEM_VOICE by name.
SYSTEM_VOICE = PROMPT_VOICE

PROMPT_TEXT = SYSTEM_TEXT


# ── Tool implementations (Ibrahim — do not modify) ────────────────────────────

async def _get_available_slots(args: Dict) -> str:
    specialty = args.get("specialty", "general")
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
                    f"Dr. {doc['name']} (ID:{doc['id']}) — slots: "
                    + ", ".join(slots)
                )
                
    return "\n".join(result) if result else f"No available slots for {specialty} right now."


async def _get_doctor_profile(args: Dict) -> str:
    doctor_id = int(args.get("doctor_id", 0))
    async with AsyncSessionLocal() as db:
        doc = await crud.get_doctor(db, doctor_id)
    if not doc:
        return f"Doctor with ID {doctor_id} not found."
    return (
        f"Dr. {doc['name']} | Specialty: {doc['specialty']} | "
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
        f"- {a.get('date')} with Dr. {a.get('doctorName')} ({a.get('status')})"
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


async def _create_appointment(args: Dict) -> str:
    patient_id = args.get("patient_id")
    patient_name = args.get("patient_name", "Demo Patient")
    doctor_name = args.get("doctor_name", "")
    doctor_id = args.get("doctor_id")

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
    
    # Ensure we have a valid patient_id (fallback to a stable one for demo if missing)
    if not patient_id:
        patient_id = f"pat-{uuid.uuid4().hex[:8]}"

    data = {
        "patientId": patient_id,
        "patientName": patient_name,
        "doctorId": doctor_id,
        "doctorName": args.get("doctor_name", ""),
        "slotId": None, # Ignore slot_id for now as the slots table is empty in demo data
        "time": args.get("time", "09:00").split()[0].zfill(5) if ":" in args.get("time", "") else "09:00",
        "date": args.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
        "reason": args.get("complaint", "General consultation"),
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
            new_patient = Patient(id=patient_id, name=patient_name, email=f"{patient_id}@example.com")
            db.add(new_patient)
            await db.flush() # ensure patient is saved before appt
            
        created = await crud.create_appointment(db, data)
        await db.commit()
        
    return (
        f"Appointment confirmed! ID: {created.get('id')}. "
        f"Date: {data['date']} at {data['time']}."
    )


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
    "get_available_slots":   _get_available_slots,
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
            return obj
            
        # Alternative format (used by some models)
        if "name" in obj and obj["name"] in TOOL_MAP:
            return {"tool": obj["name"], "args": obj.get("arguments", obj.get("args", {}))}
            
        # Recovery: if they sent raw args for create_appointment without the "tool" wrapper
        if "patient_id" in obj or "patient_name" in obj:
            return {"tool": "create_appointment", "args": obj}
        if "specialty" in obj:
            return {"tool": "get_available_slots", "args": obj}
            
    except (ValueError, json.JSONDecodeError):
        pass
    return None


async def _run_react_loop(
    messages: List[Dict],
    system: str,
    language: str,
    mode: str,
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
            response = await llm_router.call(
                messages=messages,
                task_type=task_type,
                system=system,
                temperature=0.2,
            )
            response_text = response.text.strip()
        except AllProvidersExhausted:
            logger.error("All LLM providers exhausted in BookingAgent")
            return RECOVERY_MSG.get(language, RECOVERY_MSG["en"])

        tool_call = _parse_tool_call(response_text)

        if tool_call is None:
            # If the model is narrating instead of calling a tool, nudge it once.
            if any(kw in response_text.lower() for kw in ("check", "find", "looking", "let me")):
                logger.info("BookingAgent: Nudging model to use tool instead of narrating")
                messages.append({"role": "assistant", "content": response_text})
                messages.append({"role": "user", "content": "Please provide the tool call in JSON format now. Do not narrate."})
                continue
            return response_text

        # Execute tool
        tool_name = tool_call["tool"]
        tool_args = tool_call.get("args", {})

        # Context injection: tagging channel for Activity Feed
        if tool_name == "create_appointment":
            if "booking_channel" not in tool_args:
                tool_args["booking_channel"] = "chat" if mode == "text" else "voice_note"

        logger.info("BookingAgent tool call: %s args=%s", tool_name, tool_args)

        try:
            tool_result = await TOOL_MAP[tool_name](tool_args)
        except Exception as e:
            logger.error("Tool %s failed: %s", tool_name, e)
            tool_result = f"Tool {tool_name} failed: {str(e)}"

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
                    return final_resp.text.strip()
                return response_text
            except Exception:
                pass

    return response_text


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
        response_text = await _run_react_loop(
            messages, system, language, mode, task_type=task_type
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

        return AgentResponse(
            message=response_text,
            appointment_data=None,  # orchestrator or voice_service extracts this if needed
            intent=intent,
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
        "responseText": response_text,
        "agentId": "booking_agent",
        "intent": None,
        "suggestedActions": [],
    }