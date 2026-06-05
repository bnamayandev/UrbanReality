# UrbanForge — AI-Powered Urban Development Intelligence

> Place a proposed building anywhere on a 3D Toronto map and get instant AI impact analysis across 5 dimensions: **environmental**, **traffic**, **economic**, **infrastructure**, and **housing** — plus an AI-generated preview and a real 3D model — all running locally on a single GPU.

[![UrbanForge Hackathon Demo](https://youtube.com)](https://www.youtube.com/watch?v=ii_TFVcTKdI)
---

## The local AI stack

| Stage | Model | Where it runs |
|-------|-------|---------------|
| Impact narrative + scoring | **qwen3:8b** via Ollama | Local GPU |
| Building image preview | **gemini-3.1-flash-image** | Google API |
| Image → 3D model (GLB) | **Stable Fast 3D** (~1B params) | Local GPU |
| Numeric impact models | XGBoost | CPU/GPU |
| Map + 3D render | Mapbox GL + Three.js | Browser |

> **Single-GPU note:** qwen3 (~5 GB) and Stable Fast 3D (~7.3 GB peak) don't fit on an 8 GB card at once, so they run **sequentially** — the backend evicts the LLM from VRAM before each 3D job (see `backend/gpu_coordinator.py`).

---

## Quick Start

### Prerequisites
- Python 3.10+, Node.js 18+
- NVIDIA GPU (8 GB+) + [Ollama](https://ollama.com) for the local LLM
- A Mapbox token, a Google AI Studio key, and a Hugging Face account (for the gated SF3D weights)

### 1. Clone & configure environment

```bash
git clone https://github.com/Kingsolima/Nvidia-Hackathon.git
cd Nvidia-Hackathon
cp backend/.env.example backend/.env
# Edit backend/.env (see Environment Variables below)
```

### 2. Start the local LLM (Ollama)

```bash
ollama serve            # starts Ollama on port 11434 (skip if already running)
ollama pull qwen3:8b    # ~5 GB, one-time download
```

### 3. Start the backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### 4. (Optional) Set up Stable Fast 3D for 3D generation

SF3D is vendored under `rendering-pipeline/stable-fast-3d/` (pinned to a known-good
version). It pins older deps that conflict with the backend, so it builds into its
**own venv**. The model weights are gated — accept the license at
https://huggingface.co/stabilityai/stable-fast-3d, then put your token in
`backend/.env` as `HF_TOKEN`.

```bash
cd rendering-pipeline/stable-fast-3d
python3 -m venv .venv-sf3d && source .venv-sf3d/bin/activate
pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt --no-build-isolation
```

The app runs fine without this step — 3D generation just won't be available.

### 5. (Optional) Download & train ML models from Toronto Open Data

```bash
cd ml
pip install -r requirements.txt
python data_pipeline.py   # downloads Toronto Open Data → parquet files
python train_models.py    # trains XGBoost models (GPU recommended)
```

Pre-trained model files are included in `ml/models/` so this step can be skipped.

### 6. Start the frontend

```bash
cd frontend
npm install
cp .env.example .env.local
# Add your Mapbox token to .env.local: VITE_MAPBOX_TOKEN=pk.your_token_here
npm run dev
```

Open **http://localhost:5173** — click anywhere on Toronto to place a building and run impact analysis.

---

## Tech Stack & Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Frontend (React + Vite)                 │
│  Mapbox GL  ·  Three.js (3D)  ·  react-map-gl            │
│  Drop pin → building form → 5-dimension impact dashboard │
└────────────────────┬─────────────────────────────────────┘
                     │ REST + WebSocket
                     ▼
┌─────────────────────────────────────────────────────────┐
│               Backend (FastAPI, Python)                  │
│                                                          │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │  spatial.py │  │ xgb_models.py│  │  routers/      │  │
│  │  GeoParquet │  │  XGBoost     │  │  qwen3 (LLM)   │  │
│  │  500m query │  │  (instant)   │  │  + render3d    │  │
│  └─────────────┘  └──────────────┘  └────────────────┘  │
│                                                          │
│  gpu_coordinator.py — serializes LLM ↔ SF3D on one GPU   │
│  In-memory store (no database required)                  │
└───────────────┬──────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────┐
│                   Single NVIDIA GPU (8GB+)               │
│  Ollama → qwen3:8b   ·   Stable Fast 3D (image→GLB)      │
│  XGBoost device=cuda                                     │
└─────────────────────────────────────────────────────────┘
```

### Request flow

```
User places building (lat, lng, floors, type, footprint_m2)
        ↓
POST /building → saved to in-memory store
        ↓
GET /building/{id}/impact
        ↓
spatial.py — GeoParquet 500m radius query (in-memory, loaded at startup)
  → TTC stops, traffic intersections, street trees, businesses, zoning
        ↓
XGBoost (< 100 ms, no GPU needed):
  energy_model.json   → annual kWh + environmental score
  traffic_model.json  → daily vehicle trips + traffic score
  economic_model.json → construction jobs + economic score
        ↓
qwen3:8b (localhost:11434) → narrative descriptions + infrastructure & housing scores
  (rule-based fallback if the LLM times out — demo safe)
        ↓
5-dimension blended result → cached in memory → rendered in frontend

(separately) building image (gemini-3.1-flash-image) → Stable Fast 3D → GLB on the map
```

### Key API endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/building` | Create building, returns `{id, ...}` |
| GET | `/buildings` | List all buildings |
| GET | `/building/{id}/impact` | Run (or return cached) AI impact analysis |
| WS | `/chat/{session_id}` | Citizen chatbot WebSocket `{message, building_id}` |
| POST | `/generate/building-image` | AI-generated 2D building preview (Gemini) |
| POST | `/render3d/generate-3d` | Kick off a Stable Fast 3D job → `{job_id}` |
| GET | `/render3d/status/{id}` | Poll 3D job state |
| GET | `/render3d/download/{id}` | Download the finished GLB |
| GET | `/health` | Server health check |

API docs auto-generated at **http://localhost:8001/docs**

---

## How to Reproduce the Demo

### Environment Variables

Copy `backend/.env.example` to `backend/.env` and fill in the values:

```bash
# LLM — local Ollama
MODEL_URL=http://localhost:11434/v1
MODEL_NAME=qwen3:8b

# Image generation — Google (aistudio.google.com/app/apikey)
GOOGLE_API_KEY=your_google_api_key_here
GEMINI_IMAGE_MODEL=gemini-3.1-flash-image

# Stable Fast 3D — gated model, accept license then paste token
HF_TOKEN=your_huggingface_token_here

# Frontend — get a free token at mapbox.com → Account → Tokens
MAPBOX_TOKEN=your_mapbox_token_here
```

**Minimum required keys to run the demo:**
- `MAPBOX_TOKEN` — free tier on mapbox.com is sufficient
- `MODEL_URL` + `MODEL_NAME` — local Ollama with `qwen3:8b`

`GOOGLE_API_KEY` (image preview) and `HF_TOKEN` (3D generation) are optional — the app degrades gracefully without them (a Pillow silhouette stands in for the preview; 3D is simply unavailable).

### Demo buildings

Buildings are stored in memory and reset on restart. Create one via curl:

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
- **LLM latency** — qwen3:8b runs locally; first call after the model loads into VRAM is slower. A rule-based fallback fires automatically if the LLM times out.
- **Single 8 GB GPU** — qwen3 and Stable Fast 3D can't be resident at once, so they run sequentially (the LLM is evicted from VRAM before each 3D job). On a larger GPU this constraint goes away.
- **Spatial data** — spatial queries return real results only after `data_pipeline.py` has produced GeoParquet files in `data/`. Without this step, spatial context features default to zeros.
- **3D generation (Stable Fast 3D)** — requires the separate `.venv-sf3d` environment and accepting the gated HF license. Output is intentionally low-poly (~10k verts) to fit an 8 GB GPU.
- **No persistence** — all buildings and impact results are in-memory and reset on restart.
- **No authentication** — all requests use a hardcoded demo user. Do not deploy publicly without re-enabling auth.

### Next steps

- Retrain energy model on residential/commercial-only EWRB data to improve R²
- Tune the qwen3 impact system prompt (`_IMPACT_SYSTEM` in `backend/routers/buildings.py`) for more Toronto-specific narratives
- Add historical comparison: "how does this building compare to others built in this neighbourhood?"
- Integrate MPAC property assessment data for more accurate tax revenue estimates
- Add air quality model using CANUE land-use regression coefficients

---

## Repo Structure

```
UrbanForge/
├── backend/                    # FastAPI server
│   ├── routers/
│   │   ├── buildings.py        # POST/GET /building(s), GET /impact (qwen3 + XGBoost)
│   │   ├── chat.py             # WebSocket /chat/{session_id}
│   │   ├── generate.py         # POST /generate/building-image
│   │   └── render3d.py         # /render3d/* — Stable Fast 3D job API
│   ├── rendering/
│   │   ├── gemini_renderer.py  # gemini-3.1-flash-image (primary preview renderer)
│   │   └── building_renderer.py# Pillow deterministic renderer (fallback)
│   ├── sf3d_runner.py          # Subprocess wrapper around Stable Fast 3D
│   ├── gpu_coordinator.py      # Serializes LLM ↔ SF3D on one GPU
│   ├── main.py
│   ├── models.py               # Dataclass models (in-memory)
│   ├── schemas.py              # Pydantic schemas
│   ├── spatial.py              # GeoParquet 500m radius queries (in-memory)
│   ├── xgb_models.py           # XGBoost inference
│   ├── requirements.txt
│   └── .env.example
├── frontend/                   # React + Vite + Mapbox GL + Three.js
│   └── src/
├── ml/
│   ├── data_pipeline.py        # Downloads Toronto Open Data → GeoParquet
│   ├── train_models.py         # Trains XGBoost models
│   └── models/                 # Pre-trained XGBoost JSON files
├── rendering-pipeline/
│   └── stable-fast-3d/         # Stable Fast 3D (image→GLB), own .venv-sf3d
├── data/                       # GeoParquet spatial datasets (gitignored)
├── CONTEXT.md                  # Team context & session notes
└── project-blueprint.html      # Full interactive project spec
```

## License

MIT
