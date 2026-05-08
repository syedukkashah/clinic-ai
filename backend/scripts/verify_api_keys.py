
import os
import asyncio
import httpx
from dotenv import load_dotenv

# Load .env from root
load_dotenv(os.path.join(os.path.dirname(__file__), '../../.env'))

async def test_gemini_key(key, model, endpoint="generateContent"):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:{endpoint}?key={key}"
    if endpoint == "generateContent":
        payload = {"contents": [{"parts": [{"text": "Say 'OK'"}]}]}
    else: # embedContent
        payload = {"model": f"models/{model}", "content": {"parts": [{"text": "Hello"}]}}
        
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, timeout=5.0)
            return resp.status_code == 200, f"[{resp.status_code}] {resp.text[:200]}"
        except Exception as e:
            return False, str(e)

async def verify_gemini():
    print("--- Verifying Gemini API Keys ---")
    raw_keys = os.environ.get("GEMINI_API_KEYS", "")
    keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
    if not keys:
        print("No GEMINI_API_KEYS found.")
        return False
    
    all_success = True
    for i, key in enumerate(keys):
        masked_key = f"{key[:8]}...{key[-4:]}"
        success, error = await test_gemini_key(key, "gemini-2.5-flash", "generateContent")
        if success:
            print(f"Key {i+1} ({masked_key}) OK")
        else:
            print(f"Key {i+1} ({masked_key}) FAILED: {error}")
            all_success = False
    return all_success

async def test_mistral_key(key):
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": "mistral-small-latest",
        "messages": [{"role": "user", "content": "Say 'OK'"}]
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, headers=headers, timeout=5.0)
            return resp.status_code == 200, f"[{resp.status_code}] {resp.text[:200]}"
        except Exception as e:
            return False, str(e)

async def verify_mistral():
    print("\n--- Verifying Mistral API Keys ---")
    keys = (
        [k.strip() for k in os.environ.get("MISTRAL_API_KEYS", "").split(",") if k.strip()] +
        [k.strip() for k in os.environ.get("TOGETHER_API_KEYS", "").split(",") if k.strip()]
    )
    if not keys:
        print("No Mistral or Together keys found.")
        return False
    
    all_success = True
    for i, key in enumerate(keys):
        masked_key = f"{key[:8]}...{key[-4:]}"
        success, error = await test_mistral_key(key)
        if success:
            print(f"Key {i+1} ({masked_key}) OK")
        else:
            print(f"Key {i+1} ({masked_key}) FAILED: {error}")
            all_success = False
    return all_success

async def test_groq_key(key):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": "Say 'OK'"}]
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, headers=headers, timeout=5.0)
            return resp.status_code == 200, f"[{resp.status_code}] {resp.text[:100]}"
        except Exception as e:
            return False, str(e)

async def verify_groq():
    print("\n--- Verifying Groq API Keys ---")
    raw_keys = os.environ.get("GROQ_API_KEYS", "")
    keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
    if not keys:
        print("No GROQ_API_KEYS found.")
        return False
    
    all_success = True
    for i, key in enumerate(keys):
        masked_key = f"{key[:8]}...{key[-4:]}"
        success, error = await test_groq_key(key)
        if success:
            print(f"Key {i+1} ({masked_key}) OK")
        else:
            print(f"Key {i+1} ({masked_key}) FAILED: {error}")
            all_success = False
    return all_success

async def verify_deepgram():
    print("\n--- Verifying Deepgram API ---")
    key = os.environ.get("DEEPGRAM_API_KEY", "").strip()
    if not key:
        print("No DEEPGRAM_API_KEY found.")
        return False
    
    masked_key = f"{key[:8]}...{key[-4:]}"
    
    # Test 1: Speak (TTS)
    url_tts = "https://api.deepgram.com/v1/speak?model=aura-asteria-en"
    headers = {"Authorization": f"Token {key}", "Content-Type": "application/json"}
    payload = {"text": "Hello"}
    
    # Test 2: Listen (STT - pre-recorded dummy)
    url_stt = "https://api.deepgram.com/v1/listen?model=nova-3"
    
    async with httpx.AsyncClient() as client:
        try:
            # Try TTS
            resp_tts = await client.post(url_tts, json=payload, headers=headers, timeout=5.0)
            if resp_tts.status_code == 200:
                print(f"Deepgram TTS ({masked_key}) OK")
                return True
            else:
                print(f"Deepgram TTS ({masked_key}) FAILED ({resp_tts.status_code}): {resp_tts.text}")
                
            # Try STT with an empty file just to check auth
            resp_stt = await client.post(url_stt, content=b"", headers=headers, timeout=5.0)
            if resp_stt.status_code in (200, 400): # 400 is fine if it's an empty file, as long as it's not 401
                if resp_stt.status_code == 401:
                    print(f"Deepgram STT ({masked_key}) FAILED (401)")
                else:
                    print(f"Deepgram STT ({masked_key}) AUTH OK (Received {resp_stt.status_code})")
                    return True
            else:
                print(f"Deepgram STT ({masked_key}) FAILED ({resp_stt.status_code}): {resp_stt.text}")
                
            return False
        except Exception as e:
            print(f"Deepgram ({masked_key}) ERROR: {e}")
            return False

async def main():
    print("Starting Exhaustive API Key Verification...\n")
    results = await asyncio.gather(
        verify_gemini(),
        verify_mistral(),
        verify_groq(),
        verify_deepgram()
    )
    
    print("\n" + "="*40)
    if all(results):
        print("SUCCESS: ALL SERVICES HAVE WORKING KEYS")
    else:
        print("PARTIAL FAILURE: SOME KEYS OR SERVICES FAILED")
    print("="*40)

if __name__ == "__main__":
    asyncio.run(main())
