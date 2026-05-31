import os
import traceback
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

from database import engine, Base
from routers import buildings, chat, generate, trellis
from routers import buildings, chat, generate, accounts
from spatial import layers_status

# Create all tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(title="UrbanForge API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(buildings.router)
app.include_router(chat.router)
app.include_router(generate.router)
app.include_router(trellis.router)
app.include_router(accounts.router)


@app.get("/health")
def health():
    return {"status": "ok", "spatial_layers": layers_status()}


@app.get("/debug/nemotron")
async def debug_nemotron():
    """Test NeMoTron connection directly — remove before production."""
    client = AsyncOpenAI(
        base_url=os.getenv("MODEL_URL", "http://localhost:11434/v1"),
        api_key=os.getenv("NGC_API_KEY", "not-needed"),
    )
    model = os.getenv("MODEL_NAME", "nemotron-3-super:latest")
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            max_tokens=20,
            temperature=0,
        )
        msg = resp.choices[0].message
        return {
            "status": "ok",
            "model": model,
            "content": msg.content,
            "reasoning": getattr(msg, "reasoning", None),
            "raw_dict": dict(msg),
        }
    except Exception as e:
        return {
            "status": "error",
            "model": model,
            "error_type": type(e).__name__,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }
