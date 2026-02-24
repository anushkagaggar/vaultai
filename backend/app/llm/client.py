import os
import httpx
from typing import Optional

# ✅ Try the correct Ollama Cloud endpoint
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "https://api.ollama.com/v1")  # Changed from .ai to .com

async def generate_explanation(prompt: str, model: str = "phi3:mini") -> str:
    """
    Generate explanation using Ollama Cloud API.
    """
    
    if not OLLAMA_API_KEY:
        raise ValueError("OLLAMA_API_KEY not set in environment variables")
    
    # ✅ Add more detailed error logging
    url = f"{OLLAMA_BASE_URL}/chat/completions"
    
    print(f"🔍 Calling Ollama at: {url}")
    print(f"🔑 API Key present: {bool(OLLAMA_API_KEY)}")
    
    headers = {
        "Authorization": f"Bearer {OLLAMA_API_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "stream": False
    }
    
        # ✅ Enable redirect following
    async with httpx.AsyncClient(
        timeout=120.0,
        follow_redirects=True  # ✅ THIS IS THE FIX
    ) as client:
        try:
            print(f"📡 Sending request to Ollama...")
            response = await client.post(url, json=payload, headers=headers)
            
            print(f"📥 Response status: {response.status_code}")
            print(f"📥 Response body: {response.text[:200]}")
            
            response.raise_for_status()
            
            data = response.json()
            
            if "choices" in data and len(data["choices"]) > 0:
                result = data["choices"][0]["message"]["content"]
                print(f"✅ Generated {len(result)} characters")
                return result
            else:
                raise ValueError(f"Unexpected API response format: {data}")
                
        except httpx.ConnectError as e:
            print(f"❌ Connection error: {e}")
            raise Exception(f"Cannot connect to Ollama API: {str(e)}")
        except httpx.HTTPStatusError as e:
            print(f"❌ HTTP error: {e.response.status_code}")
            print(f"❌ Response: {e.response.text}")
            raise Exception(f"Ollama API error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            print(f"❌ Unexpected error: {type(e).__name__}: {e}")
            raise Exception(f"Failed to generate explanation: {str(e)}")


# ✅ Optional: Generate with streaming (for future use)
async def generate_explanation_stream(prompt: str, model: str = "phi3:mini"):
    """
    Generate explanation with streaming.
    Yields chunks of text as they arrive.
    """
    
    if not OLLAMA_API_KEY:
        raise ValueError("OLLAMA_API_KEY not set")
    
    url = f"{OLLAMA_BASE_URL}/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {OLLAMA_API_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True
    }
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", url, json=payload, headers=headers) as response:
            response.raise_for_status()
            
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    chunk = line[6:]  # Remove "data: " prefix
                    if chunk.strip() == "[DONE]":
                        break
                    
                    try:
                        import json
                        data = json.loads(chunk)
                        if "choices" in data and len(data["choices"]) > 0:
                            delta = data["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                    except json.JSONDecodeError:
                        continue