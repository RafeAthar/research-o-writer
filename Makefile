SHELL := /bin/bash

# Backend virtualenv. All backend targets run through it so a global
# uvicorn/alembic/pytest is never required.
VENV := backend/.venv
BIN := $(VENV)/bin

.PHONY: help install install-backend install-frontend up down logs ps backend-shell migrate revision lint test fmt frontend-dev backend-dev worker seed reset eval-ingest eval eval-chat

help:
	@echo "Targets:"
	@echo "  install        Install backend (venv) + frontend deps"
	@echo "  up             Start postgres + redis + minio (docker-compose up -d)"
	@echo "  down           Stop and remove containers"
	@echo "  logs           Tail compose logs"
	@echo "  backend-dev    Run FastAPI locally (uvicorn --reload)"
	@echo "  frontend-dev   Run Next.js dev server"
	@echo "  worker         Run the RQ ingest+embed worker"
	@echo "  migrate        Apply Alembic migrations"
	@echo "  revision m=...  Create a new Alembic autogenerate revision"
	@echo "  lint           Lint backend (ruff) and frontend (eslint)"
	@echo "  fmt            Format backend (ruff format) and frontend (next lint --fix)"
	@echo "  test           Run backend pytest"
	@echo "  eval-ingest    Upload the synthetic eval articles to the running backend"
	@echo "  eval           Run retrieval-only eval (no Anthropic key needed)"
	@echo "  eval-chat      Run full eval including chat scoring (needs ANTHROPIC_API_KEY)"
	@echo "  reset          Drop volumes (WARNING: wipes db, minio, redis)"

install: install-backend install-frontend

install-backend:
	python3 -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	cd backend && ../$(BIN)/pip install -e ".[dev]"

install-frontend:
	cd frontend && npm install

up:
	docker compose up -d postgres redis minio minio-bootstrap

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

ps:
	docker compose ps

# Load the repo-root .env into the environment for recipes that need it.
# Backend config also reads it directly, but the frontend (Next.js) only sees
# NEXT_PUBLIC_* vars that are present in its process environment.
LOAD_ENV := set -a; [ -f .env ] && . ./.env; set +a;

backend-dev:
	$(LOAD_ENV) cd backend && .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend-dev:
	$(LOAD_ENV) cd frontend && npm run dev

migrate:
	$(LOAD_ENV) cd backend && .venv/bin/alembic upgrade head

revision:
	@if [ -z "$(m)" ]; then echo "Usage: make revision m='message'"; exit 1; fi
	$(LOAD_ENV) cd backend && .venv/bin/alembic revision --autogenerate -m "$(m)"

lint:
	cd backend && .venv/bin/ruff check .
	cd frontend && npm run lint

fmt:
	cd backend && .venv/bin/ruff format . && .venv/bin/ruff check --fix .

test:
	cd backend && .venv/bin/pytest

worker:
	$(LOAD_ENV) cd backend && .venv/bin/python -m app.workers.run_worker ingest embed

eval-ingest:
	$(LOAD_ENV) cd backend && .venv/bin/python scripts/upload_eval_articles.py --wait

eval:
	$(LOAD_ENV) cd backend && .venv/bin/python -m app.eval.run --file eval_data/eval_set.json

eval-chat:
	$(LOAD_ENV) cd backend && .venv/bin/python -m app.eval.run --file eval_data/eval_set.json --with-chat

reset:
	docker compose down -v
