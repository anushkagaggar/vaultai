import os
import httpx
from typing import Optional

OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")
OLLAMA_BASE_URL=os.getenv("OLLAMA_BASE_URL", "https://api.ollama.com/v1")

async def generate_explanation(prompt: str, model: str = "phi3") -> str:
    """
    Generate explanation using Ollama Cloud API.
    """
    
    if not OLLAMA_API_KEY:
        raise ValueError("OLLAMA_API_KEY not set")
    
    url = "https://api.ollama.com/v1/chat/completions"
    
    print(f"🔍 Calling Ollama at: {url}")
    print(f"🔑 API Key (first 10 chars): {OLLAMA_API_KEY[:10]}...")
    
    # ✅ Try different auth formats
    headers_variants = [
        # Format 1: Bearer token (standard)
        {
            "Authorization": f"Bearer {OLLAMA_API_KEY}",
            "Content-Type": "application/json",
        },
        # Format 2: X-API-Key header (some APIs use this)
        {
            "X-API-Key": OLLAMA_API_KEY,
            "Content-Type": "application/json",
        },
        # Format 3: API-Key header
        {
            "API-Key": OLLAMA_API_KEY,
            "Content-Type": "application/json",
        },
        # Format 4: Just the key in Authorization
        {
            "Authorization": OLLAMA_API_KEY,
            "Content-Type": "application/json",
        },
    ]
    
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
    
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        
        # Try each auth format
        for i, headers in enumerate(headers_variants):
            try:
                print(f"📡 Trying auth format #{i+1}...")
                response = await client.post(url, json=payload, headers=headers)
                
                print(f"📥 Response status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        result = data["choices"][0]["message"]["content"]
                        print(f"✅ Success with auth format #{i+1}")
                        return result
                else:
                    print(f"❌ Format #{i+1} failed: {response.text[:100]}")
                    
            except Exception as e:
                print(f"❌ Format #{i+1} error: {e}")
                continue
        
        # If all failed
        raise Exception("All authentication formats failed. Check API key or endpoint.")


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
    
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
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