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
cp .env.example .env        # then edit values
make up                      # postgres + redis + minio
make migrate                 # alembic upgrade head
make backend-dev             # FastAPI on :8000
make frontend-dev            # Next.js on :3000
```

Or, all-in-one (requires deps already installed locally):

```bash
./scripts/dev.sh
```

## Make targets

See `make help`.

## Tests

```bash
make test          # backend pytest
cd frontend && npm run typecheck && npm run lint
```
