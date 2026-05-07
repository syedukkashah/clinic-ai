"""
LLM Router Service
==================

This module provides a centralized, resilient, and async-compatible router for all
Large Language Model (LLM) calls within the MediFlow backend. It is designed to be
the single point of entry for any service, agent, or task that needs to interact
with an LLM.

Key Features:
- **Provider Abstraction**: Services don't need to know which LLM provider (Groq,
  Gemini, Mistral) is being used. The router handles the specific API calls.
- **Key Rotation & Management**: It loads multiple API keys for each provider from
  environment variables and rotates through them to distribute load and avoid
  hitting single-key rate limits.
- **Rate Limit Handling**: If a key is rate-limited (HTTP 429), it is temporarily
  deactivated and the router automatically retries with the next available key.
- **Provider Fallback**: If all keys for a preferred provider are exhausted or failing,
  the router seamlessly falls back to the next provider in a predefined priority list.
- **Task-Based Routing**: Optimizes provider selection based on the task type (e.g.,
  'reasoning', 'extraction', 'voice').
- **Normalized Response**: Returns a standardized `LLMResponse` object, so the calling
  service gets a consistent output regardless of the underlying provider.
- **Error Handling**: Raises a clear `AllProvidersExhausted` error if no provider
  or key is available, preventing silent failures.

How to Use:
------------
The router is exposed as a singleton instance `llm_router`. Agents and services
should import and call it directly.

Example:
--------
```python
from backend.services.llm_router import llm_router
from backend.schemas.llm import LLMResponse

async def some_agent_function():
    messages = [{"role": "user", "content": "What is the capital of Pakistan?"}]
    
    try:
        response: LLMResponse = await llm_router.call(
            messages=messages,
            task_type="reasoning",
            system="You are a helpful assistant.",
            temperature=0.1,
        )
        print(f"LLM says: {response.text}")
        print(f"Provider used: {response.provider}")
    except AllProvidersExhausted as e:
        print(f"Error: Could not get a response from any LLM provider. {e}")

```
"""

import asyncio
import time
from itertools import cycle
from typing import Any, Dict, List, Literal, Optional

import google.generativeai as genai
import httpx
from groq import AsyncGroq, Groq
from mistralai.async_client import MistralAsyncClient
from mistralai.models.chat_completion import ChatMessage

from core.config import settings
from schemas.llm import LLMResponse

# --- Constants ---
TASK_PROVIDER_PREFERENCE = {
    "reasoning": ["gemini", "mistral", "groq"],
    "extraction": ["groq", "gemini", "mistral"],
    "urdu": ["gemini", "mistral", "groq"],
    "rag": ["gemini", "mistral", "groq"],
    "voice": ["groq", "gemini", "mistral"],
}

# --- Custom Exception ---
class AllProvidersExhausted(Exception):
    """Raised when all LLM providers and their keys have failed."""
    pass


class LLM_Router:
    def __init__(self):
        self._keys = {
            "groq": self._load_keys(settings.GROQ_API_KEYS),
            "gemini": self._load_keys(settings.GEMINI_API_KEYS),
            "mistral": self._load_keys(settings.MISTRAL_API_KEYS),
        }
        self._key_iterators = {
            provider: cycle(keys) for provider, keys in self._keys.items()
        }
        self._blocked_keys: Dict[str, float] = {}  # key -> expiry_timestamp
        self.BLOCK_DURATION_SECONDS = 60

    def _load_keys(self, keys_str: str) -> List[str]:
        """Loads comma-separated keys from a string, filtering out empty ones."""
        return [key.strip() for key in keys_str.split(",") if key.strip()]

    def _get_next_key(self, provider: str) -> Optional[str]:
        """Gets the next available (non-blocked) key for a provider."""
        if not self._keys[provider]:
            return None
        
        # Try each key once per cycle
        for _ in range(len(self._keys[provider])):
            key = next(self._key_iterators[provider])
            if self._is_key_blocked(key):
                continue
            return key
        return None

    def _is_key_blocked(self, key: str) -> bool:
        """Checks if a key is currently in the temporary block list."""
        if key not in self._blocked_keys:
            return False
        if time.time() < self._blocked_keys[key]:
            return True
        # Block has expired
        del self._blocked_keys[key]
        return False

    def _block_key(self, key: str):
        """Adds a key to the block list for a set duration."""
        self._blocked_keys[key] = time.time() + self.BLOCK_DURATION_SECONDS
        print(f"Temporarily blocking key ...{key[-4:]} for {self.BLOCK_DURATION_SECONDS} seconds.")

    async def call(
        self,
        messages: List[Dict[str, str]],
        task_type: Literal["reasoning", "extraction", "urdu", "rag", "voice"],
        system: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """
        Makes an LLM call, handling key rotation, rate limits, and provider fallback.
        """
        provider_preference = TASK_PROVIDER_PREFERENCE.get(task_type, ["gemini", "mistral", "groq"])

        last_error = None

        for provider in provider_preference:
            key = self._get_next_key(provider)
            if not key:
                continue

            try:
                if provider == "groq":
                    response = await self._call_groq(key, messages, system, temperature, max_tokens)
                elif provider == "gemini":
                    response = await self._call_gemini(key, messages, system, temperature, max_tokens)
                elif provider == "mistral":
                    response = await self._call_mistral(key, messages, system, temperature, max_tokens)
                else:
                    continue
                
                return response

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    print(f"Rate limit hit for {provider} with key ...{key[-4:]}. Blocking key and retrying.")
                    self._block_key(key)
                    last_error = e
                    # Immediately try next provider
                    continue
                else:
                    print(f"HTTP error with {provider}: {e}")
                    last_error = e
                    continue # Try next provider
            except Exception as e:
                print(f"An unexpected error occurred with {provider}: {e}")
                last_error = e
                continue # Try next provider

        raise AllProvidersExhausted(f"All LLM providers failed. Last error: {last_error}")

    async def _call_groq(self, api_key: str, messages: List[Dict[str, str]], system: Optional[str], temperature: float, max_tokens: int) -> LLMResponse:
        client = AsyncGroq(api_key=api_key)
        if system:
            messages = [{"role": "system", "content": system}] + messages
        
        chat_completion = await client.chat.completions.create(
            messages=messages,
            model="llama3-8b-8192",
            temperature=temperature,
            max_tokens=max_tokens,
        )
        text_response = chat_completion.choices[0].message.content or ""
        return LLMResponse(
            text=text_response,
            provider="groq",
            model="llama3-8b-8192",
            raw=chat_completion.to_dict()
        )

    async def _call_gemini(self, api_key: str, messages: List[Dict[str, str]], system: Optional[str], temperature: float, max_tokens: int) -> LLMResponse:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            'gemini-1.5-flash',
            system_instruction=system
        )
        
        # Gemini uses a different format for messages
        gemini_messages = [msg['content'] for msg in messages if msg['role'] == 'user']
        
        response = await model.generate_content_async(
            gemini_messages,
            generation_config=genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens
            )
        )
        
        return LLMResponse(
            text=response.text,
            provider="gemini",
            model="gemini-1.5-flash",
            raw=response.to_dict()
        )

    async def _call_mistral(self, api_key: str, messages: List[Dict[str, str]], system: Optional[str], temperature: float, max_tokens: int) -> LLMResponse:
        client = MistralAsyncClient(api_key=api_key)
        if system:
            messages = [{"role": "system", "content": system}] + messages

        mistral_messages = [ChatMessage(**msg) for msg in messages]

        chat_response = await client.chat(
            model="mistral-small-latest",
            messages=mistral_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        text_response = chat_response.choices[0].message.content or ""
        return LLMResponse(
            text=text_response,
            provider="mistral",
            model="mistral-small-latest",
            raw=chat_response.model_dump()
        )


# --- Singleton Instance ---
llm_router = LLM_Router()
