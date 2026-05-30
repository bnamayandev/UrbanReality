#!/usr/bin/env bash
# UrbanForge — one-command startup
# Usage:  bash start.sh
# Opens:  http://100.93.45.108:5173

set -e
REPO="$HOME/UrbanForge"
VENV="$HOME/venv"

echo ""
echo "=== UrbanForge Startup ==="

# ── 1. Pull latest code ──────────────────────────────────────────────────────
echo "[1/5] Pulling latest code..."
cd "$REPO" && git pull --ff-only

# ── 2. Ollama ────────────────────────────────────────────────────────────────
echo "[2/5] Checking Ollama..."
if pgrep -x ollama > /dev/null; then
  echo "      Ollama already running."
else
  echo "      Starting Ollama..."
  tmux new-session -d -s ollama 'ollama serve'
  sleep 3
fi

# ── 3. Backend ───────────────────────────────────────────────────────────────
echo "[3/5] Starting backend (port 8001)..."
tmux kill-session -t backend 2>/dev/null || true
fuser -k 8001/tcp 2>/dev/null || true
sleep 1
tmux new-session -d -s backend \
  "cd $REPO/backend && source $VENV/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8001"
sleep 4

# health check
if curl -sf http://localhost:8001/health > /dev/null; then
  echo "      Backend OK"
else
  echo "      WARNING: backend not responding yet — check: tmux attach -t backend"
fi

# ── 4. Frontend ──────────────────────────────────────────────────────────────
echo "[4/5] Starting frontend (port 5173)..."
tmux kill-session -t frontend 2>/dev/null || true

# Make sure .env exists and has no VITE_API_BASE (use Vite proxy)
if [ ! -f "$REPO/frontend/.env" ]; then
  echo "VITE_MAPBOX_TOKEN=${MAPBOX_TOKEN:-}" > "$REPO/frontend/.env"
fi

# Install node_modules if missing
if [ ! -d "$REPO/frontend/node_modules" ]; then
  echo "      Installing npm deps..."
  cd "$REPO/frontend" && npm install
fi

tmux new-session -d -s frontend \
  "cd $REPO/frontend && npm run dev"
sleep 3

# ── 5. Done ──────────────────────────────────────────────────────────────────
echo "[5/5] All services up."
echo ""
echo "  Frontend:  http://100.93.45.108:5173"
echo "  Backend:   http://100.93.45.108:8001"
echo "  Health:    http://100.93.45.108:8001/health"
echo ""
echo "  Logs:"
echo "    tmux attach -t backend"
echo "    tmux attach -t frontend"
echo "    tmux attach -t ollama"
echo ""
