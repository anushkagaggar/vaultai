import time
import httpx
import json
from typing import AsyncIterator

from app.config import settings

# ✅ Configuration — read from settings (loaded via config.py / pydantic-settings)
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# ─────────────────────────────────────────────────────────────────────────────
# Main Generation Function
# ─────────────────────────────────────────────────────────────────────────────

async def generate_explanation(
    prompt: str,
    model: str = "llama-3.1-8b-instant",
    plan_type: str = "unknown",   # LLMOps: passed from calling node
) -> str:
    """
    Generate explanation using Groq API (free tier).

    Available models:
    - llama-3.1-8b-instant (fast, balanced)
    - llama-3.1-70b-versatile (best quality)
    - mixtral-8x7b-32768 (long context)

    LLMOps addition: plan_type is used for Prometheus label and MLflow
    tracking. The default "unknown" keeps all existing call sites working
    without any change.
    """
    
    if not settings.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set in environment variables")
    
    url = f"{GROQ_BASE_URL}/chat/completions"
    
    print(f"🔍 Calling Groq with model: {model}")
    
    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 1000
    }

    # ── LLMOps Phase 3: start latency timer ──────────────────────────────
    t0 = time.perf_counter()

    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        try:
            print(f"📡 Sending request to Groq...")
            response = await client.post(url, json=payload, headers=headers)
            
            print(f"📥 Response status: {response.status_code}")
            
            response.raise_for_status()
            
            data = response.json()
            result = data["choices"][0]["message"]["content"]

            # ── LLMOps Phase 1+2+3: record metrics on success ─────────────
            latency_ms        = round((time.perf_counter() - t0) * 1000, 1)
            usage             = data.get("usage", {})
            prompt_tokens     = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)

            # Phase 1 — structured log
            try:
                from app.agents.ops_logger import log_llm_call
                log_llm_call(plan_type, model, prompt_tokens,
                             completion_tokens, latency_ms, degraded=False)
            except Exception:
                pass

            # Phase 2 — MLflow
            try:
                from app.agents.mlflow_tracker import track_llm_call
                track_llm_call(plan_type, model, prompt_tokens,
                               completion_tokens, latency_ms,
                               prompt_text=prompt[:500], explanation=result)
            except Exception:
                pass

            # Phase 3 — Prometheus
            try:
                from app.metrics import llm_latency, token_counter
                llm_latency.labels(plan_type).observe(latency_ms / 1000)
                token_counter.labels("prompt").inc(prompt_tokens)
                token_counter.labels("completion").inc(completion_tokens)
            except Exception:
                pass

            print(f"✅ Generated {len(result)} characters")
            return result
            
        except httpx.HTTPStatusError as e:
            # ── LLMOps Phase 1: log degraded call ────────────────────────
            latency_ms = round((time.perf_counter() - t0) * 1000, 1)
            try:
                from app.agents.ops_logger import log_llm_call
                log_llm_call(plan_type, model, 0, 0, latency_ms, degraded=True)
            except Exception:
                pass
            print(f"❌ HTTP error: {e.response.status_code}")
            print(f"❌ Response: {e.response.text}")
            raise Exception(f"Groq API error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            print(f"❌ Unexpected error: {type(e).__name__}: {e}")
            raise Exception(f"Failed to generate explanation: {str(e)}")


# ─────────────────────────────────────────────────────────────────────────────
# Optional: Streaming Function (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

async def generate_explanation_stream(
    prompt: str, 
    model: str = "llama-3.1-8b-instant"
) -> AsyncIterator[str]:
    """
    Generate explanation with streaming using Groq API.
    Yields chunks of text as they arrive.
    """
    if not settings.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set")
    
    url = f"{GROQ_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 1000,
        "stream": True
    }
    
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        try:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        chunk = line[6:]
                        if chunk.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(chunk)
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                if "content" in delta:
                                    yield delta["content"]
                        except json.JSONDecodeError:
                            continue
        except httpx.HTTPStatusError as e:
            raise Exception(f"Groq streaming error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise Exception(f"Streaming failed: {str(e)}")