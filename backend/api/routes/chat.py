from fastapi import APIRouter, Request

from agents.booking_agent import process_chat_message
from schemas import schemas

router = APIRouter()


@router.post("/message", response_model=schemas.ChatResponse)
async def post_chat_message(request: Request, chat_msg: schemas.ChatMessage):
    redis_client = getattr(request.app.state, "redis", None)
    return await process_chat_message(chat_msg.userId, chat_msg.message, redis_client)
