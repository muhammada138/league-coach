from groq import AsyncGroq
from ..state import GROQ_API_KEY

async def get_coaching_feedback(system_prompt: str, user_prompt: str) -> str:
    if not GROQ_API_KEY:
        return "No API key configured."
    groq_client = AsyncGroq(api_key=GROQ_API_KEY)
    completion = await groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return completion.choices[0].message.content

async def ask_coach_question(system_prompt: str, history: list, question: str) -> str:
    if not GROQ_API_KEY:
        return "No API key configured."
    groq_client = AsyncGroq(api_key=GROQ_API_KEY)
    messages = [
        {"role": "system", "content": system_prompt},
        *history,
        {"role": "user", "content": question},
    ]
    completion = await groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        max_tokens=300,
    )
    return completion.choices[0].message.content
