from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import Building, Impact, ChatSession
from agents.chat_agent import run_chat, fallback_chat

router = APIRouter(tags=["chat"])


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

            # Load building context if provided
            building_context = None
            if building_id:
                building = db.query(Building).filter(Building.id == building_id).first()
                impact = db.query(Impact).filter(Impact.building_id == building_id).first()
                if building:
                    building_context = {
                        "name": building.name,
                        "type": building.type,
                        "floors": building.floors,
                        "footprint_m2": building.footprint_m2,
                        "status": building.status,
                        "impact": impact.summary_json if impact else None,
                    }

            history = session.messages_json or []

            try:
                reply = await run_chat(message, building_context, history)
            except Exception:
                reply = fallback_chat(message)

            # Persist conversation history
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": reply})
            session.messages_json = history
            db.commit()

            await websocket.send_json({"response": reply})

    except WebSocketDisconnect:
        pass
