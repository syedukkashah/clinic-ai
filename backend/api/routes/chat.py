from fastapi import APIRouter, Request

from agents.booking_agent import process_chat_message
from schemas import schemas
from services import voice_service

router = APIRouter()


@router.post("/message", response_model=schemas.ChatResponse)
async def post_chat_message(request: Request, chat_msg: schemas.ChatMessage):
    redis_client = getattr(request.app.state, "redis", None)
    return await process_chat_message(chat_msg.userId, chat_msg.message, redis_client)


@router.post("/voice/process", response_model=schemas.VoiceResponse)
async def post_voice_process(voice_req: schemas.VoiceProcess):
    return await voice_service.process_voice_input(voice_req.userId, voice_req.audioDataBase64)
