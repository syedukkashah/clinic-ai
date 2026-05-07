import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from services.llm_router import AllProvidersExhausted, LLM_Router
from schemas.llm import LLMResponse

# --- Test Fixtures ---

@pytest.fixture
def mock_settings():
    """Fixture to mock the settings object with test API keys."""
    with patch('services.llm_router.settings') as mock:
        mock.GROQ_API_KEYS = "gsk_key1,gsk_key2"
        mock.GEMINI_API_KEYS = "gem_key1,gem_key2"
        mock.MISTRAL_API_KEYS = "mis_key1,mis_key2"
        yield mock

@pytest.fixture
def llm_router(mock_settings):
    """Fixture to provide a fresh LLM_Router instance for each test."""
    return LLM_Router()

# --- Test Cases ---

def test_loads_keys_from_env(llm_router):
    """Tests that the router correctly loads and parses comma-separated keys."""
    assert llm_router._keys["groq"] == ["gsk_key1", "gsk_key2"]
    assert llm_router._keys["gemini"] == ["gem_key1", "gem_key2"]
    assert llm_router._keys["mistral"] == ["mis_key1", "mis_key2"]

def test_key_rotation(llm_router):
    """Tests that the router cycles through keys for a provider."""
    assert llm_router._get_next_key("groq") == "gsk_key1"
    assert llm_router._get_next_key("groq") == "gsk_key2"
    assert llm_router._get_next_key("groq") == "gsk_key1" # Should cycle back

def test_blocked_key_is_skipped(llm_router):
    """Tests that a temporarily blocked key is skipped during key selection."""
    llm_router._block_key("gsk_key1")
    assert llm_router._get_next_key("groq") == "gsk_key2"
    # The next call should also be gsk_key2 as gsk_key1 is still blocked
    assert llm_router._get_next_key("groq") == "gsk_key2"

def test_blocked_key_expires(llm_router):
    """Tests that a blocked key becomes available again after the block duration."""
    llm_router.BLOCK_DURATION_SECONDS = 0.1
    llm_router._block_key("gem_key1")
    assert llm_router._get_next_key("gemini") == "gem_key2"
    time.sleep(0.2)
    assert llm_router._is_key_blocked("gem_key1") is False
    # Now it should be able to return gem_key1 again
    assert llm_router._get_next_key("gemini") == "gem_key1"


@pytest.mark.asyncio
@patch('services.llm_router.LLM_Router._call_gemini', new_callable=AsyncMock)
async def test_successful_call(mock_call_gemini, llm_router):
    """Tests a successful call using the preferred provider."""
    mock_call_gemini.return_value = LLMResponse(text="Success", provider="gemini", model="gemini-1.5-flash")
    
    response = await llm_router.call(
        messages=[{"role": "user", "content": "Hello"}],
        task_type="reasoning" # Prefers Gemini
    )
    
    assert response.text == "Success"
    assert response.provider == "gemini"
    mock_call_gemini.assert_called_once()


@pytest.mark.asyncio
@patch('services.llm_router.LLM_Router._call_mistral', new_callable=AsyncMock)
@patch('services.llm_router.LLM_Router._call_gemini', new_callable=AsyncMock)
async def test_fallback_provider_is_used(mock_call_mistral, mock_call_gemini, llm_router):
    """Tests that the router falls back to the next provider if the first one fails."""
    # Gemini (first choice for reasoning) will fail
    mock_call_gemini.side_effect = Exception("Gemini is down")
    # Mistral (second choice) will succeed
    mock_call_mistral.return_value = LLMResponse(text="Fallback success", provider="mistral", model="mistral-small")

    response = await llm_router.call(
        messages=[{"role": "user", "content": "Hello"}],
        task_type="reasoning"
    )

    assert response.text == "Fallback success"
    assert response.provider == "mistral"
    mock_call_gemini.assert_called()
    mock_call_mistral.assert_called_once()


@pytest.mark.asyncio
@patch('services.llm_router.LLM_Router._call_groq', new_callable=AsyncMock)
async def test_rate_limit_blocks_key_and_retries(mock_call_groq, llm_router):
    """
    Tests that a 429 error blocks the key and the router retries with the next key
    from the same provider.
    """
    # First call with gsk_key1 will raise 429, second call with gsk_key2 will succeed
    mock_call_groq.side_effect = [
        httpx.HTTPStatusError("Rate limit exceeded", request=MagicMock(), response=MagicMock(status_code=429)),
        LLMResponse(text="Success on retry", provider="groq", model="llama3-8b-8192")
    ]

    response = await llm_router.call(
        messages=[{"role": "user", "content": "Extract data"}],
        task_type="extraction" # Prefers Groq
    )

    assert response.text == "Success on retry"
    assert response.provider == "groq"
    assert llm_router._is_key_blocked("gsk_key1") is True
    assert llm_router._is_key_blocked("gsk_key2") is False
    assert mock_call_groq.call_count == 2


@pytest.mark.asyncio
@patch('services.llm_router.LLM_Router._call_groq', new_callable=AsyncMock)
@patch('services.llm_router.LLM_Router._call_gemini', new_callable=AsyncMock)
@patch('services.llm_router.LLM_Router._call_mistral', new_callable=AsyncMock)
async def test_all_providers_exhausted_error(mock_groq, mock_gemini, mock_mistral, llm_router):
    """
    Tests that AllProvidersExhausted is raised when all providers and keys fail.
    """
    # Make all providers fail
    mock_groq.side_effect = Exception("Groq is down")
    mock_gemini.side_effect = Exception("Gemini is down")
    mock_mistral.side_effect = Exception("Mistral is down")

    with pytest.raises(AllProvidersExhausted):
        await llm_router.call(
            messages=[{"role": "user", "content": "Hello"}],
            task_type="reasoning"
        )
    
    # It should try each key for each provider once
    # Reasoning order: gemini, mistral, groq
    assert mock_gemini.call_count == 2 # gem_key1, gem_key2
    assert mock_mistral.call_count == 2 # mis_key1, mis_key2
    assert mock_groq.call_count == 2 # gsk_key1, gsk_key2
