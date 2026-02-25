import os
import httpx
import json
from typing import AsyncIterator

# ✅ Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# ─────────────────────────────────────────────────────────────────────────────
# Main Generation Function
# ─────────────────────────────────────────────────────────────────────────────

async def generate_explanation(prompt: str, model: str = "llama-3.1-8b-instant") -> str:
    """
    Generate explanation using Groq API (free tier).
    
    Available models:
    - llama-3.1-8b-instant (fast, balanced)
    - llama-3.1-70b-versatile (best quality)
    - mixtral-8x7b-32768 (long context)
    """
    
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set in environment variables")
    
    url = f"{GROQ_BASE_URL}/chat/completions"
    
    print(f"🔍 Calling Groq with model: {model}")
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 1000
    }
    
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        try:
            print(f"📡 Sending request to Groq...")
            response = await client.post(url, json=payload, headers=headers)
            
            print(f"📥 Response status: {response.status_code}")
            
            response.raise_for_status()
            
            data = response.json()
            result = data["choices"][0]["message"]["content"]
            
            print(f"✅ Generated {len(result)} characters")
            return result
            
        except httpx.HTTPStatusError as e:
            print(f"❌ HTTP error: {e.response.status_code}")
            print(f"❌ Response: {e.response.text}")
            raise Exception(f"Groq API error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            print(f"❌ Unexpected error: {type(e).__name__}: {e}")
            raise Exception(f"Failed to generate explanation: {str(e)}")


# ─────────────────────────────────────────────────────────────────────────────
# Optional: Streaming Function (for future use)
# ─────────────────────────────────────────────────────────────────────────────

async def generate_explanation_stream(
    prompt: str, 
    model: str = "llama-3.1-8b-instant"
) -> AsyncIterator[str]:
    """
    Generate explanation with streaming using Groq API.
    Yields chunks of text as they arrive.
    
    Args:
        prompt: The prompt to send to the model
        model: Model name (default: llama-3.1-8b-instant)
    
    Yields:
        Text chunks as they are generated
    
    Usage:
        async for chunk in generate_explanation_stream(prompt):
            print(chunk, end="", flush=True)
    """
    
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set")
    
    url = f"{GROQ_BASE_URL}/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 1000,
        "stream": True  # ✅ Enable streaming
    }
    
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        try:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    # Groq uses Server-Sent Events (SSE) format
                    if line.startswith("data: "):
                        chunk = line[6:]  # Remove "data: " prefix
                        
                        # Check for stream end
                        if chunk.strip() == "[DONE]":
                            break
                        
                        try:
                            data = json.loads(chunk)
                            
                            # Extract content from delta
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                if "content" in delta:
                                    yield delta["content"]
                                    
                        except json.JSONDecodeError:
                            # Skip malformed JSON lines
                            continue
                            
        except httpx.HTTPStatusError as e:
            raise Exception(f"Groq streaming error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise Exception(f"Streaming failed: {str(e)}")