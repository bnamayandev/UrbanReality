#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

# Initialize conda so `conda run` is available in non-interactive shells
CONDA_SH="$HOME/miniconda3/etc/profile.d/conda.sh"
if [ -f "$CONDA_SH" ]; then
  # shellcheck source=/dev/null
  source "$CONDA_SH"
else
  echo "ERROR: conda not found at $CONDA_SH — adjust the path in dev.sh" >&2
  exit 1
fi

# Install npm deps if missing
if [ ! -d "$ROOT/frontend/node_modules" ]; then
  echo "Installing npm deps..."
  cd "$ROOT/frontend" && npm install
fi

# Kill both on Ctrl+C
cleanup() {
  echo ""
  echo "Shutting down..."
  kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Backend
echo "Starting backend on :8001..."
cd "$ROOT/backend"
conda run -n trellis2 --no-capture-output python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload &
BACKEND_PID=$!

# Frontend (foreground — Ctrl+C stops both)
echo "Starting frontend on :5173..."
cd "$ROOT/frontend"
npm run dev
