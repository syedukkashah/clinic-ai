def process_chat_message(user_id: str, message: str):
    msg = message.lower()
    if "book" in msg or "appointment" in msg:
        return {
            "response": "I can help with booking. Which doctor would you like to see?",
            "agentId": "booking_agent",
            "intent": "booking_intent",
            "suggestedActions": [{"kind": "show_doctors"}],
        }
    return {"response": "How can I help you today?", "agentId": "booking_agent", "intent": "general_query"}
