# Research-o-Writer

A personal, source-grounded research and writing workspace: ingest your own
library (PDF / DOCX / EPUB / HTML / Markdown), chunk and embed it into a vector
store, then chat and write against it with Claude — every claim grounded in a
real passage with a citation. See `docs/` for the planning documents (concept,
phases, technical decisions, TODO).

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

## Architecture at a glance

The full local flow needs **four** moving parts running at once:

| Part | Started by | Port | What it does |
|---|---|---|---|
| Infra (Postgres + Redis + MinIO) | `make up` | 5432 / 6379 / 9000–9001 | Vector store, job queue, file storage |
| API | `make backend-dev` | 8000 | FastAPI — uploads, chat, export |
| Frontend | `make frontend-dev` | 3000 | Next.js UI |
| Worker | `make worker` | — | Parses, chunks, and **embeds** uploaded sources |

Uploading a source returns immediately and enqueues a job. The **worker** is
what actually parses, chunks, and embeds it — without it running, sources stay
stuck before `ready` and chat retrieval finds nothing.

## Prerequisites

- **Docker** (for Postgres + Redis + MinIO)
- **Python 3.11+**
- **Node 20+**
- **GNU make**
- **pandoc** on your PATH (only needed for DOCX export)

> **macOS note:** if you have a Homebrew Postgres or Postgres.app running, it
> will occupy port **5432** and conflict with the Docker Postgres. Stop it
> first (see [Troubleshooting](#troubleshooting)).

## Quick start

```bash
cp .env.example .env        # then edit values — see "Configuration" below
make install                # backend venv (backend/.venv) + frontend npm deps
make up                     # start postgres + redis + minio (Docker)
make migrate                # apply database schema (alembic upgrade head)

# Run these in separate terminals (all long-running):
make backend-dev            # FastAPI on http://localhost:8000
make frontend-dev           # Next.js on http://localhost:3000
make worker                 # RQ worker — REQUIRED to ingest uploaded sources
```

Open http://localhost:3000, upload a source, and once the worker marks it
`ready` you can chat against it.

Or, all-in-one (assumes deps are already installed and infra is up):

```bash
./scripts/dev.sh
```

## Configuration

All settings live in the repo-root `.env` (copied from `.env.example`). The
backend reads it directly; the Makefile also loads it for recipes that shell
out. **Restart the backend/worker after editing `.env`** — settings are cached
at process start.

Key groups:

- **`APP_AUTH_TOKEN`** — single-user auth in Phase 1. Set it to a long random
  string and use the same value for `NEXT_PUBLIC_AUTH_TOKEN`.
- **`ANTHROPIC_API_KEY`** — required for chat/synthesis (Claude). Embeddings and
  reranking do *not* use Claude.
- **Postgres / Redis / MinIO** — default to `localhost` so a host-run backend
  reaches the dockerised infra via published ports. Leave as-is unless you run
  the backend *inside* the compose network (then use service names).

### Embedding & reranking backends

Selected by `EMBEDDING_PROVIDER` and `RERANKER_PROVIDER`:

- **`local`** — run the models in-process (BGE-M3 embedder + cross-encoder
  reranker). No network, full privacy, but ~4.5 GB RAM for both. First use
  downloads the models to the HuggingFace cache.
- **`voyage`** — offload to the Voyage AI API. Frees that RAM (the default,
  chosen for ≤8 GB machines), but sends chunk text and queries to a third
  party. Requires `VOYAGE_API_KEY`.
- **`off`** (reranking only) — skip reranking and keep the RRF fusion order.
  This is the **reranker default** — it's a quality boost, not a requirement.

Shipped defaults: `EMBEDDING_PROVIDER=voyage`, `RERANKER_PROVIDER=off`.

> **Voyage free tier:** `voyage-3` is fixed at 1024 dims (a drop-in for the
> pgvector column) and is covered by the 200M-token free tier — **series 3
> only; voyage-4 is paid.** A free account with no card is throttled to 3 RPM /
> 10K TPM; adding a payment method lifts that while series 3 stays free up to
> 200M tokens. Leave `VOYAGE_OUTPUT_DIMENSION` blank for voyage-3 (it rejects
> the override).

> **Switching providers requires re-embedding** existing sources — Voyage and
> BGE vectors live in different spaces. The `embedding_model_version` column
> tracks which model produced each vector.

If you turn embeddings/reranking **on locally** and have RAM to spare, set
`WARM_MODELS_ON_STARTUP=true` to preload the models at API startup so the first
chat isn't slowed by the load. Default is `false` to protect low-RAM machines.

## Make targets

| Target | What it does |
|---|---|
| `make install` | Install backend (creates `backend/.venv`, `pip install -e .[dev]`) **and** frontend (`npm install`). |
| `make install-backend` | Backend venv + deps only. |
| `make install-frontend` | Frontend npm deps only. |
| `make up` | Start Postgres + Redis + MinIO in Docker (`docker compose up -d`), plus the one-shot MinIO bucket bootstrap. |
| `make down` | Stop and remove the containers (**keeps** volumes/data). |
| `make reset` | `docker compose down -v` — **drops volumes, wiping db, MinIO, and Redis.** Use for a clean slate. |
| `make logs` | Tail the compose logs. |
| `make ps` | Show compose container status. |
| `make migrate` | Apply Alembic migrations (`alembic upgrade head`). |
| `make revision m='...'` | Autogenerate a new Alembic migration from model changes. |
| `make backend-dev` | Run FastAPI locally with auto-reload on :8000. |
| `make frontend-dev` | Run the Next.js dev server on :3000. |
| `make worker` | Run the RQ worker for the `ingest` + `embed` queues. **Required** to process uploads. |
| `make lint` | Lint backend (ruff) and frontend (eslint). |
| `make fmt` | Format backend (ruff format + `--fix`). |
| `make test` | Run backend pytest (uses `backend/.venv`). |
| `make eval-ingest` | Upload the synthetic eval articles to the running backend. |
| `make eval` | Run the retrieval-only eval (no Anthropic key needed). |
| `make eval-chat` | Run the full eval including chat scoring (needs `ANTHROPIC_API_KEY`). |

Run `make help` for the same list from the terminal.

## Tests

```bash
make test                                  # backend pytest
cd frontend && npm run typecheck && npm run lint
```

## Troubleshooting

**`Bind for 0.0.0.0:5432 failed: port is already allocated`** — another
Postgres is using the port (commonly a Homebrew or Postgres.app install on
macOS). Find and stop it:

```bash
lsof -nP -iTCP:5432 -sTCP:LISTEN     # identify the process
brew services stop postgresql@16     # if Homebrew (use the version shown)
# or quit Postgres.app from the menu bar
```

The same rogue Postgres also causes **`password authentication failed for user
"row"`** — your app connects to *it* instead of the Docker container, and it
has different roles. Stopping it resolves both.

**`Connection refused` on `localhost:6379` (or 5432/9000)** — infra isn't
running. Run `make up` and give it a few seconds; check `make ps`.

**`password authentication failed` even with the right `.env`** — Postgres only
applies `POSTGRES_PASSWORD` when it *first* initializes its data volume. If you
changed the password after the volume already existed, either reset the role
from inside the container:

```bash
docker compose exec postgres psql -U row -d research_o_writer \
  -c "ALTER ROLE row WITH PASSWORD 'row_dev_password';"
```

or wipe and re-init (loses ingested data): `make reset && make up && make migrate`.

**A source never reaches `ready`** — the worker isn't running. Start `make
worker` and watch its output.

**Settings changes don't take effect** — restart `make backend-dev` and `make
worker`; `.env` is read once at process start.
