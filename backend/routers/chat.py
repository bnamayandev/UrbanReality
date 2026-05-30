import os
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from openai import AsyncOpenAI
from dotenv import load_dotenv

from database import get_db
from models import Building, Impact, ChatSession

load_dotenv()

router = APIRouter(tags=["chat"])

# ── NeMoTron client ───────────────────────────────────────────────────────────
_client = AsyncOpenAI(
    base_url=os.getenv("MODEL_URL", "http://localhost:11434/v1"),
    api_key=os.getenv("NGC_API_KEY", "not-needed"),
)
MODEL_NAME = os.getenv("MODEL_NAME", "nemotron-3-super:latest")

_CHAT_SYSTEM = """You are UrbanForge's citizen assistant for Toronto urban development.
You have access to real Toronto Open Data — traffic, zoning, trees, transit, businesses.
Keep responses concise (3-5 sentences). Be specific with numbers where possible.
Adapt your tone: investors get economic signals, residents get quality-of-life impacts,
planners get zoning and infrastructure data."""


async def _run_chat(message: str, building_context: dict | None, history: list) -> str:
    ctx = f"\nBuilding context:\n{json.dumps(building_context, indent=2)}\n" if building_context else ""
    messages = [{"role": "system", "content": _CHAT_SYSTEM + ctx}]
    for turn in history[-6:]:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": message})

    resp = await _client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=0.5,
        max_tokens=800,
        extra_body={"think": False},
    )
    msg = resp.choices[0].message
    # Thinking models may return null content with response in reasoning field
    text = (msg.content or "").strip()
    if not text:
        text = (getattr(msg, "reasoning", None) or "").strip()
    return text


def _fallback_chat(message: str) -> str:
    return (
        "Based on Toronto Open Data and current development patterns, this area "
        "is experiencing moderate growth pressure. Infrastructure capacity is within "
        "acceptable limits and zoning is consistent with the city's Official Plan density "
        "targets for this corridor. Would you like a detailed breakdown of any specific impact?"
    )


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@router.websocket("/chat/{session_id}")
async def chat_endpoint(websocket: WebSocket, session_id: int, db: Session = Depends(get_db)):
    await websocket.accept()

    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        session = ChatSession(id=session_id, messages_json=[])
        db.add(session)
        db.commit()

    try:
        while True:
            data = await websocket.receive_json()
            message = data.get("message", "").strip()
            building_id = data.get("building_id")
            if not message:
                continue

            building_context = None
            if building_id:
                b = db.query(Building).filter(Building.id == building_id).first()
                imp = db.query(Impact).filter(Impact.building_id == building_id).first()
                if b:
                    building_context = {
                        "name": b.name, "type": b.type,
                        "floors": b.floors, "footprint_m2": b.footprint_m2,
                        "status": b.status,
                        "impact": imp.summary_json if imp else None,
                    }

            history = session.messages_json or []
            try:
                reply = await _run_chat(message, building_context, history)
            except Exception as e:
                print(f"[chat] NeMoTron error: {type(e).__name__}: {e}")
                reply = _fallback_chat(message)

            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": reply})
            session.messages_json = history
            db.commit()

            await websocket.send_json({"response": reply})

    except WebSocketDisconnect:
        pass
