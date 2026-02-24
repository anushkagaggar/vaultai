import os
import httpx
from typing import Optional

# ✅ Ollama Cloud Configuration
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")
OLLAMA_BASE_URL = "https://api.ollama.ai/v1"  # Ollama Cloud endpoint

async def generate_explanation(prompt: str, model: str = "phi3:mini") -> str:
    """
    Generate explanation using Ollama Cloud API.
    
    Args:
        prompt: The prompt to send to the model
        model: Model name (default: phi3)
    
    Returns:
        Generated text response
    """
    
    if not OLLAMA_API_KEY:
        raise ValueError("OLLAMA_API_KEY not set in environment variables")
    
    url = f"{OLLAMA_BASE_URL}/chat/completions"
    
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
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract the response text
            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"]
            else:
                raise ValueError("Unexpected API response format")
                
        except httpx.HTTPStatusError as e:
            raise Exception(f"Ollama API error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
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