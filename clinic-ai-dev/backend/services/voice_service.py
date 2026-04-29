import base64


async def process_voice_input(user_id: str, audio_base64: str):
    transcript = "I'd like to book an appointment for tomorrow morning."
    return {
        "transcript": transcript,
        "responseText": "Sure, I have an opening at 9:00 AM with Dr. Chen. Does that work?",
        "responseAudioBase64": base64.b64encode(b"mock_audio_data").decode("utf-8"),
    }
