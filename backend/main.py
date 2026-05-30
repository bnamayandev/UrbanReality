from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
from routers import buildings, chat, generate
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


@app.get("/health")
def health():
    return {"status": "ok", "spatial_layers": layers_status()}
