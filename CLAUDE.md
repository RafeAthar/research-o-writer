# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

**Research-o-Writer** — a personal, source-grounded research and writing
workspace. Ingest a private library (PDF / DOCX / EPUB / HTML / Markdown),
chunk and embed it into pgvector, then chat and write against it with Claude
where every claim is grounded in a real passage with a citation.

Single-user in Phase 1, but the schema is multi-tenant from day one (every row
carries `user_id`). See the design docs before making structural changes.

## Read these docs first (and keep them current)

The `docs/` folder is the source of truth for *why* the code looks the way it
does. Consult the relevant one before non-trivial work, and **update it in the
same change** when a decision or scope shifts.

| File | What it holds | Read / update when |
|---|---|---|
| `docs/CONCEPT.md` | Product vision, one-liner, target user | Read for intent; rarely changes |
| `docs/PHASES.md` | The four delivery phases + Phase 0 | Read before starting a feature — confirm it belongs to the current phase |
| `docs/TODO.md` | Phase-wise working checklist | **Tick items as you complete them; add new ones as they emerge** |
| `docs/TECHNICAL_DECISIONS.md` | Architectural choices with rationale | Read before changing stack/architecture; **append a dated note when a decision changes** (e.g. the 2026-05 pluggable-backends block) |
| `docs/EVAL.md` | The retrieval/prompt eval harness | Read before touching chunking, retrieval, or prompts |

**Rule from the docs:** no retrieval or prompt change ships without running the
eval (`make eval`). Keep that gate.

## Architecture & where things live

Backend is FastAPI + RQ workers; data in Postgres + pgvector; files in MinIO
(S3-compatible); frontend is Next.js. The full local flow needs **four**
processes: infra (`make up`), API (`make backend-dev`), frontend
(`make frontend-dev`), and the **worker** (`make worker`) that does the actual
ingest/embed — uploads stay stuck without it.

```
backend/app/
  config.py            All settings (pydantic-settings); reads repo-root .env, cached via get_settings()
  db.py, deps.py       Async engine/session + FastAPI deps
  main.py              App wiring; _warm_models() preloads only *local* providers
  api/                 Route modules: chat, search, sources, projects, highlights, quotes
  services/
    chunker.py         Structure-aware chunking (~300-800 tokens, citation fields per chunk)
    embedder.py        Pluggable: local (BGE-M3) | voyage. embed_texts / embed_query / model_version
    reranker.py        Pluggable: local (cross-encoder) | voyage | off. rerank(query, candidates)
    voyage.py          Shared Voyage REST client (httpx). No SDK — it caps at Python <3.14
    search.py          hybrid_search: pgvector + FTS, RRF fusion, optional cross_rerank
    model_gateway.py   The single chokepoint for Claude calls (swap/meter/observe here)
    rag_prompt.py      Grounded-answer prompt construction
    writing_passes.py  Long-form writing flows
    export.py          Markdown/DOCX export (DOCX needs pandoc on PATH)
    metadata_enrichment.py, storage.py, parsers/, csl/
  models/              SQLAlchemy: source, project, chat, library, user (+ base)
  workers/             ingest.py, embed.py, queue.py, run_worker.py
  eval/                run.py, runner.py, schema.py
backend/alembic/       Migrations (make migrate / make revision m='...')
frontend/              Next.js app (app/, components/, lib/)
scripts/dev.sh         All-in-one local dev launcher
```

## Conventions

- **Settings are cached** (`@lru_cache get_settings()`): restart `backend-dev`
  and `worker` after editing `.env`.
- **Pluggable providers**: `EMBEDDING_PROVIDER` (local|voyage) and
  `RERANKER_PROVIDER` (local|voyage|off). Defaults: voyage embed, rerank off —
  chosen for the builder's 8 GB machine. Keep `embedder.py`/`reranker.py`
  provider-symmetric (a `local` and a `voyage` path behind one dispatch fn).
- **Switching embedding provider requires re-embedding** existing sources
  (different vector space). `embedding_model_version` tracks which model made
  each vector.
- **Vector column is `Vector(1024)`** — both BGE-M3 and voyage-3 are 1024-dim,
  so they're drop-in. Don't change the dim without a migration + re-embed plan.
- **All Claude calls go through `model_gateway.py`** — don't call the Anthropic
  SDK directly from feature code.
- **Citation precision**: each chunk stores source_id, chapter_path,
  page_start/end, paragraph_index, char_start/end, text. Preserve these through
  chunking changes (see TECHNICAL_DECISIONS §4).
- **Lint/format**: `make lint` (ruff + eslint), `make fmt` (ruff format+fix).
  Ruff selects E,F,W,I,B,UP,RUF,SIM; line-length 100 handled by formatter.
- **Python 3.11+** target; the builder's venv is 3.14, so avoid deps that cap
  below it (that's why we use Voyage via REST, not the `voyageai` SDK).

## Common commands

```bash
make up           # start postgres + redis + minio (Docker)
make migrate      # alembic upgrade head
make backend-dev  # FastAPI :8000
make frontend-dev # Next.js :3000
make worker       # RQ ingest+embed worker (REQUIRED for uploads to process)
make test         # backend pytest
make lint / fmt   # ruff + eslint / ruff format
make eval         # retrieval eval (gate for retrieval/prompt changes)
make reset        # docker compose down -v — WIPES db/minio/redis
```

See `README.md` for full setup and a troubleshooting section.

## Gotchas (already hit — don't rediscover)

- **Port 5432 conflict / `password authentication failed for user "row"`**: an
  orphan/other Docker container (or a native Postgres) holding 5432 means the
  app connects to the wrong server. `lsof -nP -iTCP:5432 -sTCP:LISTEN`, stop the
  squatter, then `make up`. (See README troubleshooting.)
- **Postgres password only applies on first volume init.** Changing
  `POSTGRES_PASSWORD` after the volume exists won't take — `ALTER ROLE` inside
  the container, or `make reset` to re-init.
- **Empty env var → pydantic error**: blank values for typed-optional settings
  (e.g. `VOYAGE_OUTPUT_DIMENSION=`) need a `field_validator(mode="before")` to
  coerce "" → None. Leave it blank for voyage-3 (it rejects dim overrides).
- **Voyage free tier is series-3 only** (200M tokens); voyage-4 is paid.

## Git workflow

- Develop on branch `claude/research-writing-assistant-lQYC1`.
- Commit with clear messages; push with `git push -u origin <branch>`.
- **Do not open a PR unless explicitly asked.**
- Never commit secrets (`.env`, keys). `.env.example` is the tracked template.
