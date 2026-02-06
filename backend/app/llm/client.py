import os
import openai

openai.api_key = os.getenv("OPENAI_API_KEY")

async def generate_explanation(prompt: str) -> str:

    response = await openai.ChatCompletion.acreate(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are a financial data explainer. Do not invent numbers."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.2
    )

    return response.choices[0].message.content.strip()
