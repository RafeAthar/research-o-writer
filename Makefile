SHELL := /bin/bash

.PHONY: help up down logs ps backend-shell migrate revision lint test fmt frontend-dev backend-dev seed reset

help:
	@echo "Targets:"
	@echo "  up             Start postgres + redis + minio (docker-compose up -d)"
	@echo "  down           Stop and remove containers"
	@echo "  logs           Tail compose logs"
	@echo "  backend-dev    Run FastAPI locally (uvicorn --reload)"
	@echo "  frontend-dev   Run Next.js dev server"
	@echo "  migrate        Apply Alembic migrations"
	@echo "  revision m=...  Create a new Alembic autogenerate revision"
	@echo "  lint           Lint backend (ruff) and frontend (eslint)"
	@echo "  fmt            Format backend (ruff format) and frontend (next lint --fix)"
	@echo "  test           Run backend pytest"
	@echo "  reset          Drop volumes (WARNING: wipes db, minio, redis)"

up:
	docker compose up -d postgres redis minio minio-bootstrap

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

ps:
	docker compose ps

backend-dev:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend-dev:
	cd frontend && npm run dev

migrate:
	cd backend && alembic upgrade head

revision:
	@if [ -z "$(m)" ]; then echo "Usage: make revision m='message'"; exit 1; fi
	cd backend && alembic revision --autogenerate -m "$(m)"

lint:
	cd backend && ruff check .
	cd frontend && npm run lint

fmt:
	cd backend && ruff format . && ruff check --fix .

test:
	cd backend && pytest

reset:
	docker compose down -v
