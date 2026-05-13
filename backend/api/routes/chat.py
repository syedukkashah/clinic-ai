from fastapi import APIRouter

from agents.orchestrator import orchestrator
from schemas import schemas

router = APIRouter()


@router.post("/message", response_model=schemas.ChatResponse)
async def post_chat_message(chat_msg: schemas.ChatMessage):
    response = await orchestrator.handle_booking(
        transcript=chat_msg.message,
        session_id=chat_msg.userId,
        lang=chat_msg.lang,
        mode="text",
    )
    return {
        "response": response.message,
        "responseText": response.message,
        "agentId": "orchestrator",
        "intent": response.intent,
        "suggestedActions": [],
    }
