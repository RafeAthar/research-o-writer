#!/usr/bin/env bash
set -euo pipefail

# One-command local startup. Brings infra up, runs migrations, starts backend + frontend.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -f .env ]; then
  echo ".env not found; copying from .env.example. EDIT IT before continuing."
  cp .env.example .env
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

echo "Starting infra (postgres, redis, minio)..."
docker compose up -d postgres redis minio minio-bootstrap

echo "Waiting for postgres..."
until docker compose exec -T postgres pg_isready -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" >/dev/null 2>&1; do
  sleep 1
done

echo "Running migrations..."
( cd backend && alembic upgrade head )

echo "Starting backend (uvicorn) and frontend (next dev) in background..."
( cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port "${APP_PORT:-8000}" ) &
BACKEND_PID=$!
( cd frontend && npm run dev ) &
FRONTEND_PID=$!

echo ""
echo "Backend  PID=$BACKEND_PID  http://localhost:${APP_PORT:-8000}/healthz"
echo "Frontend PID=$FRONTEND_PID http://localhost:3000"
echo "Press Ctrl-C to stop."

trap 'kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true' INT TERM
wait
