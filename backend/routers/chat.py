import os
import json
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from openai import AsyncOpenAI
from dotenv import load_dotenv

from database import _buildings, _impacts, _impact_modules
from gpu_coordinator import gpu_lock_async

load_dotenv()

router = APIRouter(tags=["chat"])

_client = AsyncOpenAI(
    base_url=os.getenv("MODEL_URL", "http://localhost:11434/v1"),
    api_key=os.getenv("NGC_API_KEY", "not-needed"),
)
MODEL_NAME = os.getenv("MODEL_NAME", "qwen3:8b")

_CHAT_SYSTEM = """You are UrbanForge's citizen assistant for Toronto urban development.
You have access to real Toronto Open Data - traffic, zoning, trees, transit, businesses.
Keep responses concise (3-5 sentences). Be specific with numbers where possible.
Adapt your tone: investors get economic signals, residents get quality-of-life impacts,
planners get zoning and infrastructure data."""


async def _run_chat(message: str, building_context: dict | None, history: list) -> str:
    ctx = f"\nSubmission context:\n{json.dumps(building_context, indent=2)}\n" if building_context else ""
    messages = [{"role": "system", "content": _CHAT_SYSTEM + ctx}]
    messages.extend(history[-6:])
    messages.append({"role": "user", "content": message})
    # Share the single GPU with SF3D: wait if a 3D job is running.
    async with gpu_lock_async():
        resp = await _client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.5,
            max_tokens=800,
            extra_body={"think": False},
        )
    msg = resp.choices[0].message
    text = (msg.content or "").strip()
    if not text:
        text = (getattr(msg, "reasoning", None) or "").strip()
    return text


def _fallback_chat(message: str) -> str:
    return (
        "Based on Toronto Open Data and current development patterns, this area "
        "is experiencing moderate growth pressure. Infrastructure capacity appears "
        "manageable, but the final recommendation should consider zoning, transit, "
        "tree canopy, traffic, and neighbourhood vulnerability together."
    )


def _building_context(building_id: str) -> dict | None:
    try:
        key = str(uuid.UUID(str(building_id)))
    except (TypeError, ValueError):
        return None

    b = _buildings.get(key)
    if not b:
        return None

    impact = _impacts.get(key)
    modules = []
    if impact:
        modules = [
            {
                "module_name": m.module_name,
                "score": m.score,
                "summary": m.summary,
                "details": m.details,
            }
            for m in _impact_modules.get(str(impact.id), [])
        ]

    return {
        "project_name": b.project_name,
        "building_type": b.building_type,
        "proposed_height_m": float(b.proposed_height_m or 0),
        "proposed_floor_area_sqm": float(b.proposed_floor_area_sqm or 0),
        "proposed_units": b.proposed_units,
        "status": b.status,
        "analysis": {
            "overall_score": impact.overall_score if impact else None,
            "narrative_summary": impact.narrative_summary if impact else None,
            "modules": modules,
        },
    }


@router.websocket("/chat/{session_id}")
async def chat_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    history = []
    try:
        while True:
            data = await websocket.receive_json()
            message = data.get("message", "").strip()
            building_id = data.get("building_id")
            if not message:
                continue

            building_context = _building_context(building_id) if building_id else None
            try:
                reply = await _run_chat(message, building_context, history)
            except Exception as e:
                print(f"[chat] NeMoTron error: {type(e).__name__}: {e}")
                reply = _fallback_chat(message)

            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": reply})
            await websocket.send_json({"response": reply})
    except WebSocketDisconnect:
        pass
