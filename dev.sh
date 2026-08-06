#!/usr/bin/env bash
# Start the backend (FastAPI, :8000) and frontend (Vite) together with one
# command. Installs dependencies on first run if they're missing.
#
# Usage:
#   ./dev.sh          # normal app
#   ./dev.sh demo     # demo mode (auto-loads sample data)
#
# Ctrl+C stops both.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

MODE="${1:-dev}"
if [ "$MODE" != "dev" ] && [ "$MODE" != "demo" ]; then
  echo "Usage: ./dev.sh [demo]" >&2
  exit 1
fi

if [ ! -d .venv ]; then
  echo "==> Creating Python virtualenv (.venv)"
  uv venv --python 3.12
fi

if ! .venv/bin/python -c "import fathom" >/dev/null 2>&1; then
  echo "==> Installing backend dependencies"
  uv pip install -e ".[dev]"
fi

if [ ! -d frontend/node_modules ]; then
  echo "==> Installing frontend dependencies"
  (cd frontend && npm install)
fi

pids=()
cleanup() {
  echo
  echo "==> Stopping…"
  for pid in "${pids[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

echo "==> Starting backend on http://localhost:8000"
.venv/bin/python -m uvicorn fathom.api.app:app --port 8000 --reload &
pids+=("$!")

if [ "$MODE" = "demo" ]; then
  echo "==> Starting frontend (demo) — open the URL Vite prints below"
  echo "    First run seeds sample data: near-instant with no ANTHROPIC_API_KEY set,"
  echo "    or up to ~1-2 min if it's set (each estimate calls the real LLM). Give it"
  echo "    time rather than reloading or opening a second tab mid-seed."
else
  echo "==> Starting frontend (dev) — open the URL Vite prints below"
fi
(cd frontend && npm run "$MODE")
