# UrbanForge — Running the Intelligence Layer

This document covers how to start the full UrbanForge stack on the **DGX Spark (GX10)**.  
The intelligence layer = Ollama running NeMoTron locally on the GPU + FastAPI backend + React frontend.

---

## What's running

| Service | Port | What it does |
|---|---|---|
| Ollama | 11434 | Runs `nemotron-3-super:latest` (86GB) on the GB10 GPU |
| FastAPI backend | 8001 | XGBoost models + NeMoTron impact analysis + spatial queries |
| Vite frontend | 5173 | React map UI |

---

## One-command startup (recommended)

SSH into the DGX, then:

```bash
cd ~/UrbanForge && bash start.sh
```

Open in browser: **`http://100.93.45.108:5173`**

That's it. The script pulls the latest code, checks Ollama, kills any stale processes, and starts everything in tmux.

---

## Manual startup (if start.sh fails)

### 1. Make sure Ollama is running
```bash
pgrep ollama && echo "running" || ollama serve &
```

### 2. Start the backend
```bash
fuser -k 8001/tcp 2>/dev/null || true
cd ~/UrbanForge/backend
source ~/venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8001
```

### 3. Start the frontend (separate terminal or tmux pane)
```bash
cd ~/UrbanForge/frontend
npm run dev
```

---

## Environment — backend `.env`

File lives at `~/UrbanForge/backend/.env`. Required values:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost/urbanforge
MODEL_URL=http://localhost:11434/v1
MODEL_NAME=nemotron-3-super:latest
NGC_API_KEY=not-needed
```

**If NeMoTron chat/impact returns generic fallback responses**, the `MODEL_NAME` is wrong. Fix:
```bash
sed -i 's/MODEL_NAME=.*/MODEL_NAME=nemotron-3-super:latest/' ~/UrbanForge/backend/.env
```

Then restart the backend.

---

## Verify everything works

```bash
# Backend health + spatial layers loaded
curl http://localhost:8001/health

# NeMoTron connection test (should return "status": "ok")
curl http://localhost:8001/debug/nemotron

# Run full validation suite (92 checks)
cd ~/UrbanForge/backend && source ~/venv/bin/activate && python tests/validate.py
```

---

## Checking logs

```bash
tmux attach -t backend    # backend logs (Ctrl-B D to detach)
tmux attach -t frontend   # frontend logs
tmux attach -t ollama     # ollama logs
tmux ls                   # list all sessions
```

---

## How the intelligence pipeline works

```
User places building on map (lat/lng + type + floors + footprint)
        ↓
POST /building  →  saved to PostgreSQL
        ↓
GET /building/{id}/impact
        ↓
┌─────────────────────────────────────────────┐
│  XGBoost models (fast, local, no GPU)        │
│  • energy_model.json     → kWh/m² intensity │
│  • energy_gas_model.json → gas consumption  │
│  • economic_model.json   → construction jobs│
│  • ITE calculator        → daily trips + TTC│
│    proximity discount (Toronto Open Data)   │
└─────────────────────────────────────────────┘
        ↓ scores + descriptions
┌─────────────────────────────────────────────┐
│  NeMoTron on DGX Spark (GPU, ~15-45s)        │
│  • Gets building spec + spatial context     │
│    (traffic volumes, TTC stops, zoning,     │
│     street trees, parks, businesses)        │
│  • Generates infrastructure + housing       │
│    analysis (dimensions XGB doesn't cover) │
│  • XGBoost scores OVERRIDE NeMoTron scores  │
│    for env/traffic/economic (more reliable) │
└─────────────────────────────────────────────┘
        ↓ blended result cached in DB
Frontend renders 5 impact scores + descriptions
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `localhost refused to connect` on port 5173 | Frontend not started or not exposed | `cd ~/UrbanForge/frontend && npm run dev` (needs `host: 0.0.0.0` in vite.config.js — already set) |
| Backend offline | Port 8001 in use or wrong directory | `fuser -k 8001/tcp && cd ~/UrbanForge/backend && source ~/venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8001` |
| Chat returns same generic text every time | Wrong `MODEL_NAME` in `.env` | Run the sed command above to fix MODEL_NAME |
| Infrastructure/Housing scores look like formulas | NeMoTron failing, using rule-based fallback | Check `/debug/nemotron` endpoint for the exact error |
| `No module named 'fastapi'` | Running uvicorn without the venv | Always `source ~/venv/bin/activate` first |
| Energy score too low (like 5/100) | Stale cached impact from old code | `curl -X DELETE http://localhost:8001/building/{id}/impact` |
