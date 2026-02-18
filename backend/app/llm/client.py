import httpx


OLLAMA_URL = "https://river-mystagogic-supernationally.ngrok-free.dev"
MODEL_NAME = "phi3:mini"


async def generate_explanation(prompt: str) -> str:

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }

    headers = {
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=180) as client:

        resp = await client.post(
            OLLAMA_URL,
            json=payload,
            headers=headers
        )

        print("LLM STATUS:", resp.status_code)
        print("LLM RAW:", resp.text)

        resp.raise_for_status()

        data = resp.json()

        return data["response"].strip()
