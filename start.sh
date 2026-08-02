#!/usr/bin/env bash
# Launcher: sets up and runs both the backend (FastAPI) and frontend (Vite dev
# server), then opens the app in your browser. Safe to re-run -- it skips any
# setup step that's already done (existing venv, installed deps, existing .env).
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
LOG_DIR="$SCRIPT_DIR/logs"
BACKEND_PORT=8000
FRONTEND_PORT=5173

echo "== Voice PDF Book Q&A -- Launcher =="
echo ""

# 1. Prerequisite checks
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found. Install Python 3.11+ from https://www.python.org/downloads/ and re-run this script."
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "ERROR: npm not found. Install Node.js 18+ from https://nodejs.org/ and re-run this script."
  exit 1
fi

# 2. Free up the ports in case a previous run didn't shut down cleanly
free_port() {
  local port="$1"
  local pids
  pids="$(lsof -ti:"$port" 2>/dev/null || true)"
  if [ -n "$pids" ]; then
    echo "Port $port is in use -- stopping the existing process so this run can use it..."
    kill $pids 2>/dev/null || true
    sleep 1
  fi
}
free_port "$BACKEND_PORT"
free_port "$FRONTEND_PORT"

# 3. Backend virtual environment
if [ ! -d "$BACKEND_DIR/venv" ]; then
  echo "Creating Python virtual environment (backend/venv)..."
  python3 -m venv "$BACKEND_DIR/venv"
fi
# shellcheck disable=SC1091
source "$BACKEND_DIR/venv/bin/activate"

echo "Installing backend dependencies (first run downloads a few hundred MB -- ML libraries + a small reranker model; can take a few minutes)..."
pip install -q --upgrade pip
pip install -q -r "$BACKEND_DIR/requirements.txt"

# 4. .env -- created empty; the OpenAI key is entered later from the app's own
# Settings page, not by hand-editing this file.
if [ ! -f "$BACKEND_DIR/.env" ]; then
  echo "Creating backend/.env (empty -- add your OpenAI API key from the app's Settings page once it's running)..."
  cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
fi

# 5. Frontend dependencies
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "Installing frontend dependencies (npm install)..."
  (cd "$FRONTEND_DIR" && npm install)
fi

mkdir -p "$LOG_DIR"

# 6. Start both servers, logging to files so this terminal stays readable
echo ""
echo "Starting backend on http://localhost:$BACKEND_PORT ..."
(cd "$BACKEND_DIR" && exec uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT") \
  >"$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!

echo "Starting frontend on http://localhost:$FRONTEND_PORT ..."
(cd "$FRONTEND_DIR" && exec npm run dev -- --port "$FRONTEND_PORT") \
  >"$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!

cleanup() {
  echo ""
  echo "Shutting down..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  exit 0
}
trap cleanup INT TERM

# 7. Wait for the backend to actually be ready before opening the browser
echo "Waiting for the backend to be ready (first run is slower -- downloading the reranker model)..."
ready=false
for _ in $(seq 1 90); do
  if curl -s -o /dev/null "http://localhost:$BACKEND_PORT/documents"; then
    ready=true
    break
  fi
  sleep 1
done
if [ "$ready" != "true" ]; then
  echo "The backend didn't come up in time. Check $LOG_DIR/backend.log for details."
fi

sleep 2  # give Vite a moment to finish its own startup

open "http://localhost:$FRONTEND_PORT" 2>/dev/null \
  || xdg-open "http://localhost:$FRONTEND_PORT" 2>/dev/null \
  || echo "Open http://localhost:$FRONTEND_PORT in your browser."

echo ""
echo "Take Home Demo is running:"
echo "  App (open this):  http://localhost:$FRONTEND_PORT"
echo "  Backend API:       http://localhost:$BACKEND_PORT"
echo "  Logs:              $LOG_DIR/backend.log, $LOG_DIR/frontend.log"
echo ""
echo "First time running? Go to Settings in the app and add your OpenAI API key."
echo "Press Ctrl+C in this window to stop the app."
echo ""

wait
