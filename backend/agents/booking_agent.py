from services.redis_memory import get_history, save_history
import logging

logger = logging.getLogger(__name__)

async def process_chat_message(user_id: str, message: str, redis_client=None):
    msg = message.lower()
    
    history = []
    if redis_client:
        try:
            history = await get_history(redis_client, user_id)
        except Exception as e:
            logger.error(f"Failed to get redis history: {e}")
            
    history.append({"role": "user", "content": message})
    
    if "book" in msg or "appointment" in msg:
        resp = "I can help with booking. Which doctor would you like to see?"
        intent = "booking_intent"
        suggested = [{"kind": "show_doctors"}]
    else:
        resp = "How can I help you today?"
        intent = "general_query"
        suggested = []
        
    history.append({"role": "assistant", "content": resp})
    
    if redis_client:
        try:
            await save_history(redis_client, user_id, history)
        except Exception as e:
            logger.error(f"Failed to save redis history: {e}")
            
    return {
        "response": resp,
        "agentId": "booking_agent",
        "intent": intent,
        "suggestedActions": suggested,
    }
