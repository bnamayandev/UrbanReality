#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

# ── Venv check ────────────────────────────────────────────────────────────────
VENV_PYTHON="$ROOT/.venv/bin/python"
if [ ! -x "$VENV_PYTHON" ]; then
  echo "ERROR: .venv not found. Create it first:" >&2
  echo "  python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt" >&2
  exit 1
fi

# ── 3D (Stable Fast 3D) + GPU ─────────────────────────────────────────────────
# SF3D runs in its own venv; override here if it lives elsewhere.
export SF3D_DIR="$ROOT/rendering-pipeline/stable-fast-3d"
export CUDA_VISIBLE_DEVICES=0

# ── npm deps ──────────────────────────────────────────────────────────────────
if [ ! -d "$ROOT/frontend/node_modules" ]; then
  echo "Installing npm deps..."
  cd "$ROOT/frontend" && npm install
fi

# ── Shutdown handler ──────────────────────────────────────────────────────────
cleanup() {
  echo ""
  echo "Shutting down..."
  kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# ── Backend ───────────────────────────────────────────────────────────────────
echo "Starting backend on :8001..."
cd "$ROOT/backend"
"$VENV_PYTHON" -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload &
BACKEND_PID=$!

# ── Frontend (foreground — Ctrl+C stops both) ─────────────────────────────────
echo "Starting frontend on :5173..."
cd "$ROOT/frontend"
npm run dev
