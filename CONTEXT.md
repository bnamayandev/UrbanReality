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

## Current state — what works

### Backend (`~/UrbanForge/backend/`) — ALMOST RUNNING
All Python deps installed. One final command before `uvicorn` starts:

```bash
sudo -u postgres psql -d urbanforge -c "CREATE EXTENSION IF NOT EXISTS postgis;"
```

Then:
```bash
cd ~/UrbanForge/backend
source ~/venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

Verify: `curl http://localhost:8001/health`

**Packages installed in venv:** fastapi, uvicorn, sqlalchemy, psycopg2-binary, geoalchemy2,
shapely, pydantic, pydantic-settings, python-dotenv, httpx, websockets, geopandas, pyarrow,
langgraph, langchain, langchain-openai, openai, pillow, scikit-learn, xgboost

**`.env` file:** already created at `~/UrbanForge/backend/.env`
- `MODEL_URL=http://localhost:11434/v1`
- `MODEL_NAME=nemotron-3-super:latest` (change to `nemotron3:33b` for faster demo)
- `DATABASE_URL=postgresql://postgres:postgres@localhost/urbanforge`
- `API_PORT=8001`

### Intelligence layer — CONFIRMED WORKING
Nemotron responds correctly via Ollama at `localhost:11434`. Tested with curl.
The model is a **thinking model** — it reasons internally before answering.
`max_tokens=1024` is set in the agents (enough for think + answer).
`max_tokens=150` is too small — the thinking alone uses that up.

### Database — NEEDS POSTGIS EXTENSION (see above)
PostgreSQL 16 installed, `urbanforge` DB created, `postgres` user password = `postgres`.
PostGIS installed but extension not yet enabled in the DB.

### AI agents — FIXED
Both `impact_agent.py` and `chat_agent.py` now use `MODEL_URL` + `MODEL_NAME` from `.env`
and use the `openai` Python client (not raw httpx).

### XGBoost models — LOADING
Three pre-trained models load on startup:
- `energy_model.json` — predicts annual kWh from building specs
- `traffic_model.json` — predicts daily vehicle trips
- `economic_model.json` — predicts construction jobs

These run instantly (no GPU needed) and supplement Nemotron's narrative analysis.

### Data pipeline — READY, NOT YET RUN
`ml/data_pipeline.py` downloads Toronto Open Data → `data/*.parquet`.
Omar needs to run it and then load into PostGIS.
Until then, the backend handles empty spatial context gracefully (falls back to XGBoost + rules).

---

## How the intelligence layer works

```
User places building (lat, lng, floors, type, material)
        ↓
FastAPI: spatial.py queries PostGIS for everything within 500m
  → traffic volumes, street trees, TTC stops, businesses, zoning
        ↓
Context + building specs → structured prompt → Nemotron (localhost:11434)
        ↓
Nemotron outputs JSON: { environmental, traffic, economic, infrastructure, housing }
  each with score (0-100) + 2-sentence description
        ↓
XGBoost scores blend in (override Nemotron where more accurate)
        ↓
Frontend renders impact dashboard
```

The model is NOT generic once Omar's data loads — it sees real Toronto numbers.

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
│   │   └── generate.py         # POST /buildings/generate-image
│   ├── main.py
│   ├── models.py               # SQLAlchemy ORM
│   ├── schemas.py              # Pydantic schemas
│   ├── spatial.py              # PostGIS radius queries
│   ├── database.py
│   ├── xgb_models.py           # XGBoost inference
│   ├── requirements.txt        # Full dep list
│   └── .env.example
├── ml/
│   ├── data_pipeline.py        # Downloads Toronto Open Data → parquet
│   ├── train_models.py         # Trains XGBoost models
│   ├── models/                 # Pre-trained XGBoost JSON files
│   └── fetch.py
├── data/
│   ├── coefficients/           # ITE trip rates, StatsCan I-O multipliers
│   └── data.md                 # Dataset guide
├── src/components/
│   └── BuildingPreview.jsx     # Three.js 3D building component (Rehan)
├── BACKEND_ISSUES.txt          # Setup guide for Wali
├── CONTEXT.md                  # This file
└── project-blueprint.html      # Full interactive spec — open in browser
```

---

## API endpoints

| Method | Endpoint | What it does |
|--------|----------|--------------|
| POST | `/building` | Create building, returns `{id, ...}` |
| GET | `/buildings` | List all buildings |
| GET | `/building/{id}/impact` | Run or return cached AI impact analysis |
| WS | `/chat/{session_id}` | WebSocket chat `{message, building_id}` |
| POST | `/buildings/generate-image` | Generate 2D building image from text |
| GET | `/health` | Server health check |

Backend accessible at: `http://100.93.45.108:8001`

---

## Immediate next steps by person

**Wali (Backend):**
1. `sudo -u postgres psql -d urbanforge -c "CREATE EXTENSION IF NOT EXISTS postgis;"`
2. Make sure ollama is serving: `curl -s http://localhost:11434/v1/models`
3. `cd ~/UrbanForge/backend && uvicorn main:app --host 0.0.0.0 --port 8001 --reload`
4. Test: `curl http://localhost:8001/health`

**Omar (Data):**
1. `cd ~/UrbanForge && source ~/venv/bin/activate`
2. `python ml/data_pipeline.py` — downloads all Toronto Open Data to `data/`
3. Write `ml/load_spatial.py` to push parquets → PostGIS tables (the spatial queries in `spatial.py` expect these)
4. Merge `omar/data` into main

**Rehan (Rendering + Frontend):**
1. Init Vite React app: `npm create vite@latest frontend -- --template react`
2. `npm install mapbox-gl react-map-gl three`
3. Set up Mapbox map with Toronto bounds, dark style
4. Wire `BuildingPreview.jsx` into the builder sidebar
5. Add `fill-extrusion` layer for 3D building placement

**Ahmed + Yusuf (AI/ML):**
- Backend is almost running — once Wali has it up, test the full pipeline:
  `POST /building` then `GET /building/1/impact`
- Tune Nemotron prompts in `backend/agents/impact_agent.py` for demo quality
- Consider switching to `nemotron3:33b` for faster demo responses
