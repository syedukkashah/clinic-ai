
import sys
import os
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).parent))

from agents.orchestrator import orchestrator
from unittest.mock import patch, AsyncMock, MagicMock
import asyncio

async def test_voice_agent_examples():
    """Test voice agent with example texts to verify orchestrator and booking agent integration"""
    output = []
    output.append("=== Testing Voice Agent with Example Texts ===")
    
    # Mock LLM router to return predefined responses
    mock_llm_response = MagicMock()
    
    example_requests = [
        ("Hello, I need a doctor appointment", "en"),
        ("مجھے ڈاکٹر سے ملنا ہے", "ur"),
        ("Can you book an appointment for tomorrow?", "en"),
        ("مجھے کل کے لئے اپوائنٹمنٹ بُک کرنے کی ضرورت ہے", "ur"),
    ]
    
    for i, (text, lang) in enumerate(example_requests, 1):
        output.append(f"\n--- Test {i} ---")
        output.append(f"Request: {text}")
        output.append(f"Language: {lang}")
        
        # Set mock response based on language
        if lang == "en":
            mock_llm_response.text = "Sure! I can help you book an appointment. What specialty do you need?"
        else:
            mock_llm_response.text = "یقیناً! میں آپ کی اپوائنٹمنٹ بُک کرنے میں مدد کر سکتا ہوں۔ آپ کو کس سپیشلٹی کی ضرورت ہے؟"
        
        with patch("agents.booking_agent.llm_router.call", AsyncMock(return_value=mock_llm_response)):
            # Test orchestrator with voice mode
            result = await orchestrator.handle_booking(
                transcript=text,
                session_id=f"test_session_{i}",
                lang=lang,
                mode="voice"
            )
        
        output.append(f"Agent Response: {result.message}")
        output.append(f"Intent detected: {result.intent}")
        output.append(f"Appointment data: {result.appointment_data}")
        assert result.message is not None, "Agent response should not be None"
        output.append(f"Test {i} passed!")
    
    output.append("\nAll voice agent example tests passed!")
    
    # Write to file
    output_file = os.path.join(os.path.dirname(__file__), "voice_agent_test_output.txt")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(output))
    
    return output

if __name__ == "__main__":
    results = asyncio.run(test_voice_agent_examples())
    print("\n".join(results))
