# UrbanForge — Session Context
> Resume from any device. Read this before asking Claude anything.
> Last updated: 2026-05-30

---

## What this project is

**UrbanForge** — NVIDIA Hackathon 2026 (Toronto, Urban Operations track). 6-person team, 36-hour build.

AI-powered urban development intelligence: place a proposed building anywhere on a Toronto 3D map, get instant AI impact analysis (environmental, traffic, economic, infrastructure, housing) powered by Nemotron running locally on a DGX Spark GPU.

Full spec: open `project-blueprint.html` in a browser.

---

## Team

| Person | Role |
|--------|------|
| Omar | Data Engineer — `omar/data` branch |
| Ben + Rehan | 3D Rendering / Maps — `rehan-rendering` branch |
| Rehan | Frontend / UX |
| Ahmed | AI / ML Engineer |
| Yusuf | Integration Lead + AI / ML |
| Wali | Backend Engineer |

---

## Hardware — DGX Spark

- **SSH:** `ssh asus@100.93.45.108` (user: `asus`, not `ahmed`)
- **GPU:** NVIDIA GB10 Grace Blackwell Superchip, CUDA 13.0
- **Repo on GPU:** `~/UrbanForge/`
- **Venv:** `~/venv/` — always `source ~/venv/bin/activate` first

### Models already downloaded (via Ollama)
| Model | Size | Use |
|-------|------|-----|
| `nemotron-3-super:latest` | 86 GB | Primary — best quality, slow (~45s/response) |
| `nemotron3:33b` | 27 GB | Faster alternative for demo |
| `qwen3.6:35b` | 23 GB | Backup — already tested working |
| `gemma4:26b` | 17 GB | Backup |

**Qwen** also runs via llama.cpp (port 8000): `./run_qwen3.6.sh` (chmod +x first)

### Services
- **Ollama** (Nemotron): `ollama serve` → port 11434
- **FastAPI backend**: `uvicorn main:app --host 0.0.0.0 --port 8001 --reload`
- Run both in tmux: `tmux new -s <name>`, detach with Ctrl+B then D

---

## Current state — BACKEND IS RUNNING ✅

### What's confirmed working (tested 2026-05-30)

```bash
# Create a building
curl -X POST http://localhost:8001/building \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Tower","type":"residential (high-rise)","floors":40,"footprint_m2":2000,"lat":43.6532,"lng":-79.3832}'
# → {"id":1,"name":"Test Tower","type":"residential (high-rise)","floors":40,...}

# Get AI impact analysis
curl http://localhost:8001/building/1/impact
# → {"building_id":1,"environmental":{"score":5,...},"traffic":{"score":100,"description":"Estimated +3449 daily vehicle trips..."},"economic":{"score":95,"description":"Estimated 1783 person-years of construction employment..."},"infrastructure":{"score":80,...},"housing":{"score":40,...}}
```

**End-to-end pipeline confirmed:** XGBoost models run instantly, NeMoTron fallback kicks in, scores + descriptions returned.

### Backend setup (already done on DGX Spark)
All deps installed in `~/venv/`. PostGIS extension enabled. DB running.

```bash
cd ~/UrbanForge/backend
source ~/venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

**Packages installed:** fastapi, uvicorn, sqlalchemy, psycopg2-binary, geoalchemy2,
shapely, pydantic, pydantic-settings, python-dotenv, httpx, websockets, geopandas, pyarrow,
langgraph, langchain, langchain-openai, openai, pillow, scikit-learn, xgboost, scipy, tiktoken, regex

**`.env` file:** at `~/UrbanForge/backend/.env`
- `MODEL_URL=http://localhost:11434/v1`
- `MODEL_NAME=nemotron-3-super:latest` (change to `nemotron3:33b` for faster demo)
- `DATABASE_URL=postgresql://postgres:postgres@localhost/urbanforge`
- `NEMORON_URL=http://localhost:11434` ← fixed (was pointing to 8001 by mistake)

---

## How the intelligence layer works

```
User places building on map (lat, lng, floors, type, material)
        ↓
POST /building  →  building saved to PostGIS DB
        ↓
GET /building/{id}/impact
        ↓
spatial.py queries PostGIS: everything within 500m
  → traffic intersections, TTC stops, street trees, businesses, zoning
        ↓
XGBoost (instant, no GPU):
  → energy_model    → annual kWh + environmental score
  → traffic_model   → daily vehicle trips + traffic score
  → economic_model  → construction jobs + economic score
        ↓
Nemotron (localhost:11434) adds narrative + infrastructure + housing scores
  (if Nemotron times out, rule-based fallback handles it — demo safe)
        ↓
Blended result: XGBoost scores + Nemotron descriptions → cached in DB
        ↓
Frontend renders 5-dimension impact dashboard
```

---

## XGBoost model status

| Model | R² | Notes |
|---|---|---|
| `traffic_model.json` | 0.978 | Working well — 3449 trips for 40-floor tower ✅ |
| `economic_model.json` | 0.993 | Working well — 1783 construction jobs ✅ |
| `energy_model.json` | 0.47 | Weak — trained on city buildings (fire stations etc), not residential. Omar needs to retrain with EWRB residential data. Environmental score currently unreliable. |

---

## API endpoints

| Method | Endpoint | What it does |
|--------|----------|--------------|
| POST | `/building` | Create building, returns `{id, ...}` |
| GET | `/buildings` | List all buildings |
| GET | `/building/{id}/impact` | Run or return cached AI impact analysis |
| WS | `/chat/{session_id}` | WebSocket chat `{message, building_id}` |
| POST | `/generate/building-image` | Generate 2D building preview from text or params |
| GET | `/health` | Server health check |

**Backend live at:** `http://100.93.45.108:8001`
**API docs (auto-generated):** `http://100.93.45.108:8001/docs`

---

## Repo structure

```
Nvidia-Hackathon/
├── backend/                    # FastAPI server (Wali)
│   ├── agents/
│   │   ├── impact_agent.py     # Nemotron impact analysis
│   │   ├── chat_agent.py       # Citizen chatbot
│   │   └── building_image_agent.py  # LangGraph 2D image generator
│   ├── rendering/
│   │   └── building_renderer.py     # Pillow deterministic renderer
│   ├── routers/
│   │   ├── buildings.py        # POST/GET /building(s), GET /impact
│   │   ├── chat.py             # WebSocket /chat/{session_id}
│   │   └── generate.py         # POST /generate/building-image
│   ├── main.py
│   ├── models.py               # SQLAlchemy ORM
│   ├── schemas.py              # Pydantic schemas
│   ├── spatial.py              # PostGIS radius queries
│   ├── database.py
│   ├── xgb_models.py           # XGBoost inference
│   ├── requirements.txt
│   └── .env.example
├── ml/
│   ├── data_pipeline.py        # Downloads Toronto Open Data → parquet
│   ├── train_models.py         # Trains XGBoost models (run after data_pipeline)
│   ├── models/                 # Pre-trained XGBoost JSON files
│   └── fetch.py
├── frontend/                   # ← TO BE BUILT (see FRONTEND.md)
├── CONTEXT.md                  # This file
├── FRONTEND.md                 # Frontend spec for Rehan/Ben
└── project-blueprint.html      # Full interactive spec — open in browser
```

---

## Immediate next steps by person

**Wali (Backend):** Done. Keep server running in tmux.

**Omar (Data):**
1. Retrain energy model — filter `ewrb_energy.parquet` to residential/commercial only (not fire stations/libraries), then `python ml/train_models.py`. Drop new `energy_model.json` in `ml/models/` and restart server.
2. Run `ml/data_pipeline.py` and load Toronto Open Data into PostGIS so spatial context is real.

**Rehan + Ben (Frontend):**
Read `FRONTEND.md` — everything you need is in there. API is live and tested.

**Ahmed + Yusuf (AI/ML):**
- Full pipeline is working end-to-end. 
- Next: tune Nemotron prompt in `backend/agents/impact_agent.py` — the current system prompt works but descriptions could be more Toronto-specific.
- Consider switching `MODEL_NAME` to `nemotron3:33b` in `.env` for faster demo (45s → ~15s per response).
- Plant 3-4 demo buildings in DB before demo so we're not live-calling Nemotron on stage.
