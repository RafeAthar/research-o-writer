# Research-o-Writer

A personal, source-grounded research and writing workspace. See `docs/` for
the planning documents (concept, phases, technical decisions, TODO).

## Phase 1 status

In progress on branch `claude/research-writing-assistant-lQYC1`. Track work
against `docs/TODO.md`.

## Repo layout

```
backend/    FastAPI app + Alembic migrations + RQ workers
frontend/   Next.js app
docs/       Planning documents
scripts/    Local dev helpers
.github/    CI workflows
```

## Local development

Prereqs: Docker, Python 3.11+, Node 20+, GNU make.

```bash
cp .env.example .env        # then edit values (ANTHROPIC_API_KEY, tokens)
make install                 # backend venv (backend/.venv) + frontend npm deps
make up                      # postgres + redis + minio
make migrate                 # alembic upgrade head
make backend-dev             # FastAPI on :8000
make frontend-dev            # Next.js on :3000
```

The default `.env.example` points the backend at `localhost` so `make
backend-dev` (uvicorn on your host) can reach the dockerised infra via the
published ports. DOCX export additionally requires `pandoc` on your PATH.

Or, all-in-one (requires deps already installed locally):

```bash
./scripts/dev.sh
```

## Make targets

See `make help`.

## Tests

```bash
make test          # backend pytest (uses backend/.venv)
cd frontend && npm run typecheck && npm run lint
```
