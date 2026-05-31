# UrbanForge — AI-Powered Urban Development Intelligence

> Place a proposed building anywhere on a 3D Toronto map and get instant AI impact analysis across 5 dimensions: **environmental**, **traffic**, **economic**, **infrastructure**, and **housing** — powered by NVIDIA NeMotron running locally on a DGX Spark GPU.

---

## Quick Start

### Prerequisites
- Python 3.10+, Node.js 18+
- PostgreSQL with PostGIS extension
- NVIDIA GPU + Ollama (for local LLM) **or** NVIDIA Build API key

### 1. Clone & configure environment

```bash
git clone https://github.com/Kingsolima/Nvidia-Hackathon.git
cd Nvidia-Hackathon
cp backend/.env.example backend/.env
# Edit backend/.env with your API keys (see Environment Variables section below)
```

### 2. Start the backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### 3. (Optional) Download & train ML models from Toronto Open Data

```bash
cd ml
pip install -r requirements.txt
python data_pipeline.py   # downloads Toronto Open Data → parquet files
python train_models.py    # trains XGBoost models (GPU recommended)
```

Pre-trained model files are included in `ml/models/` so this step can be skipped.

### 4. Start the frontend

```bash
cd frontend
npm install
cp .env.example .env.local
# Add your Mapbox token to .env.local: VITE_MAPBOX_TOKEN=pk.your_token_here
npm run dev
```

Open **http://localhost:5173** — click anywhere on Toronto to place a building and run impact analysis.

### 5. (DGX Spark only) Start NeMoTron via Ollama

```bash
ollama serve                          # starts Ollama on port 11434
ollama pull nemotron-3-super:latest   # ~86 GB, one-time download
# Or faster alternative for demo:
ollama pull nemotron3:33b             # ~27 GB
```

---

## Tech Stack & Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Frontend (React + Vite)             │
│  Mapbox GL  ·  Three.js (3D)  ·  react-map-gl           │
│  Drop pin → building form → 5-dimension impact dashboard│
└────────────────────┬────────────────────────────────────┘
                     │ REST + WebSocket
                     ▼
┌─────────────────────────────────────────────────────────┐
│               Backend (FastAPI, Python)                  │
│                                                         │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │  spatial.py │  │ xgb_models.py│  │  agents/      │  │
│  │  PostGIS    │  │  XGBoost     │  │  NeMoTron     │  │
│  │  500m query │  │  (instant)   │  │  (narrative)  │  │
│  └─────────────┘  └──────────────┘  └───────────────┘  │
│                                                         │
│  PostgreSQL + PostGIS (spatial DB)                      │
└───────────────┬─────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────┐
│          NVIDIA DGX Spark (GB10 Blackwell GPU)          │
│  Ollama → nemotron-3-super:latest  (86 GB, local)       │
│  XGBoost device=cuda  ·  TRELLIS.2 (3D GLB generation) │
└─────────────────────────────────────────────────────────┘
```

### Request flow

```
User places building (lat, lng, floors, type, footprint_m2)
        ↓
POST /building → saved to PostGIS DB
        ↓
GET /building/{id}/impact
        ↓
spatial.py — PostGIS 500m radius query
  → TTC stops, traffic intersections, street trees, businesses, zoning
        ↓
XGBoost (< 100 ms, no GPU needed):
  energy_model.json   → annual kWh + environmental score
  traffic_model.json  → daily vehicle trips + traffic score
  economic_model.json → construction jobs + economic score
        ↓
NeMoTron (localhost:11434) → narrative descriptions + infrastructure & housing scores
  (rule-based fallback if NeMoTron times out — demo safe)
        ↓
5-dimension blended result → cached in DB → rendered in frontend
```

### Key API endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/building` | Create building, returns `{id, ...}` |
| GET | `/buildings` | List all buildings |
| GET | `/building/{id}/impact` | Run (or return cached) AI impact analysis |
| WS | `/chat/{session_id}` | Citizen chatbot WebSocket `{message, building_id}` |
| POST | `/generate/building-image` | AI-generated 2D building preview |
| GET | `/health` | Server health check |

API docs auto-generated at **http://localhost:8001/docs**

---

## How to Reproduce the Demo

### Environment Variables

Copy `backend/.env.example` to `backend/.env` and fill in the values:

```bash
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost/urbanforge

# LLM — Ollama on DGX Spark (already running)
MODEL_URL=http://localhost:11434/v1
MODEL_NAME=nemotron-3-super:latest   # or nemotron3:33b for faster demo
NEMORON_URL=http://localhost:11434

# Image generation (priority order — first key that works is used)
OPENAI_API_KEY=your_openai_api_key_here

# TRELLIS.2 3D model generation (DGX Spark SSH)
HF_TOKEN=your_huggingface_token_here
GX10_HOST=100.93.45.108
GX10_USER=asus

# Frontend — get a free token at mapbox.com → Account → Tokens
MAPBOX_TOKEN=your_mapbox_token_here
```

**Minimum required keys to run the demo:**
- `DATABASE_URL` — local Postgres with PostGIS, or the Supabase URL in `.env.example`
- `MAPBOX_TOKEN` — free tier on mapbox.com is sufficient
- `MODEL_URL` + `MODEL_NAME` — either local Ollama or NVIDIA Build API

### Demo buildings (pre-seeded)

The backend will automatically create demo buildings in the DB on first run if the DB is empty. You can also manually create one via curl:

```bash
curl -X POST http://localhost:8001/building \
  -H "Content-Type: application/json" \
  -d '{"name":"King West Tower","type":"residential (high-rise)","floors":40,"footprint_m2":2000,"lat":43.6427,"lng":-79.3990}'
```

---

## Datasets & Synthetic Data

All Toronto Open Data is downloaded by `ml/data_pipeline.py` and stored as GeoParquet in `data/`.

| Dataset | Source | Used for |
|---------|--------|----------|
| Toronto Building Permits (Active + Cleared) | [Toronto Open Data](https://open.toronto.ca) | XGBoost training backbone |
| Toronto Energy & Water Reporting (EWRB) | Toronto Open Data | Energy/utility model training |
| Transportation Tomorrow Survey (TTS) | [DMG, U of T](https://dmg.utoronto.ca) | Traffic model training |
| Traffic Volumes at Intersections | Toronto Open Data | Traffic model + spatial context |
| Toronto Employment Survey | Toronto Open Data | Jobs model training |
| Street Tree Inventory | Toronto Open Data | Environmental impact (canopy loss) |
| TTC Stops (GTFS) | Toronto Open Data | Transit access scoring |
| Neighbourhood Profiles | Toronto Open Data | Community context |
| Zoning By-law GeoJSON | Toronto Open Data | Zoning context at pin location |

**No synthetic training data** — all ML models are trained on real City of Toronto open datasets.

**Provenance:** All source data is freely available under the [Open Government Licence – Toronto](https://open.toronto.ca/open-data-licence/). Raw downloads are not committed to this repo due to file size (~2 GB); run `ml/data_pipeline.py` to fetch and process them.

---

## Known Limitations & Next Steps

### Current limitations

- **Energy model accuracy is low (R² ≈ 0.47)** — the EWRB dataset includes non-residential buildings (fire stations, libraries) which skew predictions for high-rise residential. Environmental scores should be treated as directional, not precise.
- **NeMoTron latency** — the 86 GB model takes ~45 seconds per analysis on DGX Spark. The 33B model (~15 s) is recommended for demos. Rule-based fallback fires automatically on timeout.
- **PostGIS spatial data** — spatial queries return real results only after `data_pipeline.py` has loaded Toronto Open Data into the DB. Without this step, spatial context features default to zeros.
- **3D GLB generation (TRELLIS.2)** — requires SSH access to the DGX Spark GPU server; not available in local dev without the SSH keys configured in `.env`.
- **No authentication in demo mode** — auth was removed to simplify the hackathon demo. Do not deploy publicly without re-enabling it.

### Next steps

- Retrain energy model on residential/commercial-only EWRB data to improve R²
- Tune NeMoTron system prompt in `backend/agents/impact_agent.py` for more Toronto-specific narratives
- Add historical comparison: "how does this building compare to others built in this neighbourhood?"
- Integrate MPAC property assessment data for more accurate tax revenue estimates
- Add air quality model using CANUE land-use regression coefficients


---

## Repo Structure

```
UrbanForge/
├── backend/                    # FastAPI server
│   ├── agents/
│   │   ├── impact_agent.py     # NeMoTron impact analysis (LangGraph)
│   │   ├── chat_agent.py       # Citizen chatbot WebSocket
│   │   └── building_image_agent.py
│   ├── routers/
│   │   ├── buildings.py        # POST/GET /building(s), GET /impact
│   │   ├── chat.py             # WebSocket /chat/{session_id}
│   │   └── generate.py         # POST /generate/building-image
│   ├── rendering/
│   │   └── building_renderer.py  # Pillow deterministic renderer (fallback)
│   ├── main.py
│   ├── models.py               # SQLAlchemy ORM
│   ├── schemas.py              # Pydantic schemas
│   ├── spatial.py              # PostGIS 500m radius queries
│   ├── xgb_models.py           # XGBoost inference
│   ├── requirements.txt
│   └── .env.example
├── frontend/                   # React + Vite + Mapbox GL + Three.js
│   └── src/
├── ml/
│   ├── data_pipeline.py        # Downloads Toronto Open Data → GeoParquet
│   ├── train_models.py         # Trains XGBoost models
│   └── models/                 # Pre-trained XGBoost JSON files
├── data/                       # GeoParquet spatial datasets (gitignored)
├── TRELLIS2/                   # 3D GLB model generation
├── CONTEXT.md                  # Team context & session notes
└── project-blueprint.html      # Full interactive project spec
```

## License

MIT
