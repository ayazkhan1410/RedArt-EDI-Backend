#!/usr/bin/env bash
# ========
# Start RedArt EDI stack with Docker Compose
# Usage:
#   ./scripts/start.sh
#   ./scripts/start.sh down
#   ./scripts/start.sh logs
# ========
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

# ========
# Ensure .env exists
# ========
if [[ ! -f .env ]]; then
  echo "[start] .env missing — copying from .env.example"
  cp .env.example .env
fi

ACTION="${1:-up}"

# ========
# Actions
# ========
case "${ACTION}" in
  up|start)
    # ========
    # Build and run all services
    # ========
    echo "[start] Building and starting containers ..."
    docker compose up --build -d
    echo "[start] Stack is up."
    echo "[start] API:    http://127.0.0.1:8000/api/health/"
    echo "[start] Docs:   http://127.0.0.1:8000/api/docs/"
    echo "[start] Logs:   ./scripts/start.sh logs"
    ;;
  down|stop)
    # ========
    # Stop stack
    # ========
    docker compose down
    ;;
  logs)
    # ========
    # Follow logs
    # ========
    docker compose logs -f --tail=200
    ;;
  restart)
    # ========
    # Restart stack
    # ========
    docker compose down
    docker compose up --build -d
    ;;
  *)
    echo "Usage: ./scripts/start.sh [up|down|logs|restart]"
    exit 1
    ;;
esac
