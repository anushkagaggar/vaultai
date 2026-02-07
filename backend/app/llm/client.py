import httpx

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3:8b"

async def generate_explanation(prompt: str) -> str:

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(OLLAMA_URL, json=payload)

        resp.raise_for_status()

        data = resp.json()

        return data["response"].strip()
