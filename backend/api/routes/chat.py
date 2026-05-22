from fastapi import APIRouter, Request

from agents.orchestrator import orchestrator
from schemas import schemas

router = APIRouter()


@router.post("", response_model=schemas.ChatResponse)
@router.post("/message", response_model=schemas.ChatResponse)
async def post_chat_message(request: Request, chat_msg: schemas.ChatMessage):
    redis_client = getattr(request.app.state, "redis", None)
    response = await orchestrator.handle_booking(
        transcript=chat_msg.message,
        session_id=chat_msg.userId,
        lang=chat_msg.lang,
        mode="text",
        redis=redis_client,
    )
    return {
        "response": response.message,
        "responseText": response.message,
        "agentId": "orchestrator",
        "intent": response.intent,
        "suggestedActions": [],
        "detected_lang": chat_msg.lang,
        "appointment": getattr(response, "appointment_data", None),
        "tool_calls": getattr(response, "tool_calls", []),
        "suggestedSlots": getattr(response, "suggested_slots", []),
    }
