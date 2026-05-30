# Toronto Construction Impact Analyzer

Drop a pin on a Toronto map, describe a proposed building, and get an instant impact report:
**economy** (jobs, tax revenue, utility costs) · **environment** (trees, CO₂, air quality) · **traffic** · **community benefit score** + an AI-generated narrative — all powered by a local Blackwell GPU.

---

## Quick Start

### 1. Download & process Toronto open data
```bash
cd ml
pip install -r requirements.txt
python data_pipeline.py
```

### 2. Train the ML models (requires NVIDIA GPU)
```bash
python train_models.py
```

### 3. Start Ollama + FastAPI backend
```bash
# From the project root
docker-compose up -d
# Pull the LLM model on first run
docker exec -it nvidia-hackathon-ollama-1 ollama pull llama3.1:8b
```

### 4. Start the frontend
```bash
cd frontend
npm install
# Add your Mapbox token to .env.local
echo "NEXT_PUBLIC_MAPBOX_TOKEN=pk.your_token_here" > .env.local
npm run dev
```

Open http://localhost:3000 — click anywhere on Toronto to begin.

---

## Architecture

```
Next.js (Mapbox map + form + report card)
        │  POST /api/analyze
        ▼
FastAPI backend
  ├── Spatial lookup   → GeoParquet files (Toronto Open Data)
  ├── ML inference     → 3 XGBoost models (Blackwell GPU)
  ├── Community score  → rule-based composite
  └── LLM narrative    → Ollama llama3.1:8b (Blackwell GPU)
```

## ML Models

| Model | Inputs | Outputs |
|---|---|---|
| Economic | building type, sqft, floors, neighbourhood | jobs, tax revenue, utility cost |
| Environmental | building type, sqft, floors, nearby trees, traffic | trees at risk, CO₂/year, AQI delta |
| Traffic | building type, sqft, floors, transit access, traffic baseline | daily trips, peak congestion %, parking demand |

All three models are XGBoost regressors trained with `device=cuda` on Toronto Building Permits × spatial context features.

## Data Sources

See [`data/data.md`](data/data.md) for the complete dataset guide.

Key sources:
- Toronto Energy and Water Reporting (EWRB) — utility model training
- Toronto Building Permits — training backbone
- Toronto Employment Survey — jobs model
- Transportation Tomorrow Survey (TTS) — traffic model
- Toronto Street Trees, Neighbourhood Profiles, Zoning By-law — spatial context

## Community Benefit Score

Rule-based 0–100 composite:
- +20 residential / +10 mixed-use (housing supply)
- +15 affordable housing mentioned
- +15 / +8 / −8 transit access (distance to TTC stop)
- +10 ground-floor commercial
- −5 to −20 traffic congestion burden
- −5 to −15 tree/canopy loss
- +10 low-carbon building
