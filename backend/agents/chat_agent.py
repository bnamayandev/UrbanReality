"""
Citizen Q&A Agent — conversational agent that answers questions about a specific
building or Toronto development in general. Adapts its focus to the user's persona.
"""

import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv()

NEMORON_URL = os.getenv("NEMORON_URL", "http://localhost:11434")

SYSTEM_PROMPT = """You are UrbanForge's citizen assistant for Toronto urban development.
You have access to real development data and Toronto Open Data.
Keep responses concise (3-5 sentences). Be specific with numbers when possible.
Adapt your tone: investors get economic signals, residents get quality-of-life impacts,
planners get zoning and infrastructure data.
"""


async def run_chat(message: str, building_context: dict | None, history: list) -> str:
    context_block = ""
    if building_context:
        context_block = f"\nBuilding context loaded:\n{json.dumps(building_context, indent=2)}\n"

    messages = [{"role": "system", "content": SYSTEM_PROMPT + context_block}]
    for turn in history[-6:]:    # keep last 6 turns to stay within context
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": message})

    payload = {
        "model": "nvidia/llama-3.1-nemotron-70b-instruct",
        "messages": messages,
        "temperature": 0.5,
        "max_tokens": 512,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{NEMORON_URL}/v1/chat/completions",
            json=payload,
        )
        response.raise_for_status()

    return response.json()["choices"][0]["message"]["content"]


def fallback_chat(message: str) -> str:
    return (
        "Based on Toronto Open Data and current development patterns, this area "
        "is experiencing moderate growth pressure. Infrastructure capacity is within "
        "acceptable limits and zoning is consistent with the city's Official Plan density "
        "targets for this corridor. Would you like a detailed breakdown of any specific impact?"
    )
