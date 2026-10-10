#!/usr/bin/env bash
# Starts the HospitalGym server (FastAPI + websocket) on port 8000. Usage: ./run_server.sh [port]
# Loads .env when present; every outside service goes online only because its credential is set there.
set -euo pipefail
cd "$(dirname "$0")"
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi
PORT="${1:-${PORT:-8000}}"
if [ ! -x .venv/bin/python ]; then
  echo "No .venv found. Create it first: python3.12 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt" >&2
  exit 1
fi
exec .venv/bin/python -m uvicorn server.app:app --host "${HOST:-127.0.0.1}" --port "$PORT"
