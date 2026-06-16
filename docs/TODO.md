# Research-o-Writer — Phase-wise TODO

The working checklist. Refer to this from time to time during build. Tick
items as they are completed; add new items as scope is discovered. Linked
context lives in `CONCEPT.md`, `PHASES.md`, `TECHNICAL_DECISIONS.md`.

Convention:
- `[ ]` not started · `[~]` in progress · `[x]` done · `[-]` dropped/deferred

---

## Phase 0 — Validate the value cheaply

- [ ] Pick one real book + one real chapter we plan to write
- [ ] Try NotebookLM against it; record frustrations
- [ ] Try Anara / SciSpace against it; record frustrations
- [ ] Try a hand-rolled PaperQA setup against it; record frustrations
- [ ] Map frustrations to requirements in CONCEPT.md
- [ ] Sign off on Phase 1 scope unchanged or with explicit edits

---

## Phase 1 — MVP

### 1.1 Project bootstrap

- [ ] Initialize Python backend (FastAPI) project with linting/formatting
- [ ] Initialize Next.js frontend project with TypeScript + ESLint
- [ ] Docker Compose: Postgres (with pgvector), MinIO, Redis (for RQ)
- [ ] `.env.example`, secrets handling (no secrets committed)
- [ ] Basic CI: lint + type-check + run tests on push
- [ ] One-command local startup script

### 1.2 Data model & schema (multi-tenant from day one)

- [ ] `users` (single user in Phase 1, but table exists)
- [ ] `sources` (book/article: title, authors, year, isbn/doi, format, original_file_url, status)
- [ ] `source_structure` (TOC tree per source: chapter_path, page ranges)
- [ ] `chunks` (source_id, chapter_path, page_start/end, paragraph_index, char_start/end, text, token_count, user_id)
- [ ] `chunk_embeddings` (pgvector column with HNSW index)
- [ ] `chunk_fts` (tsvector column for FTS, GIN index)
- [ ] `highlights` (user-saved spans on a source with optional note)
- [ ] `quote_shelf` (saved quotes with citations)
- [ ] `projects` (a book/article being written)
- [ ] `outline_nodes` (tree per project)
- [ ] `evidence_cards` (link outline_node ↔ chunk/highlight)
- [x] `project_sources` (M2M project ↔ library source: a project's source shelf)
- [ ] Migrations tooling (Alembic) wired up

### 1.3 Ingestion pipeline

- [ ] File upload endpoint (multipart, virus-scan optional, size limit)
- [ ] Persist original file to MinIO with content-addressed key
- [ ] Format detection (PDF / DOCX / EPUB / MD / TXT / HTML)
- [ ] PDF parser (PyMuPDF) → structural tree + page numbers
- [ ] DOCX parser (`python-docx`) → structural tree
- [ ] EPUB parser (`ebooklib`) → structural tree
- [ ] HTML parser (`readability` + `beautifulsoup4`) → structural tree
- [ ] Markdown / TXT direct path → structural tree
- [ ] OCR fallback for scanned PDFs (Tesseract or docTR), gated by detection
- [ ] TOC extraction
- [ ] Metadata enrichment: ISBN/DOI lookup (OpenLibrary, CrossRef, Google Books)
- [ ] Structure-aware chunker (~300–800 tokens, never crosses heading)
- [ ] Chunk record includes: source_id, chapter_path, page_start/end, paragraph_index, char_start/end, text
- [ ] RQ worker that runs the pipeline async; status reporting on `sources`
- [ ] UI: ingestion status (queued / extracting / chunking / embedding / ready / failed) with error surface

### 1.4 Embedding & indexing

- [ ] Local embedding service (BGE-M3 or equivalent) with batch API
- [ ] Embed all chunks; insert into pgvector
- [ ] Build HNSW index
- [ ] Populate FTS tsvector + GIN index
- [ ] Re-embed support when embedding model changes (versioned columns)

### 1.5 Retrieval

- [ ] Semantic search endpoint (top-K via pgvector)
- [ ] Lexical / FTS search endpoint (top-K via Postgres FTS)
- [ ] Exact-phrase search support
- [ ] Hybrid retriever (merge + dedupe + rerank)
- [ ] Local cross-encoder reranker integrated
- [ ] Filters: by source, chapter, tag
- [ ] Returns chunks with full citation metadata

### 1.6 Model gateway & chat

- [ ] Model gateway abstraction (one place that calls Claude)
- [ ] Sonnet 4.6 default; Opus 4.7 for "hard synthesis" mode
- [ ] Strict-RAG prompt template: cite every claim, refuse if weak support
- [ ] Distinguish extractive vs synthetic claims in response payload
- [ ] Post-process to verify every cited chunk_id is real
- [ ] Single-source chat
- [ ] Multi-source / library-wide chat
- [x] Project-scoped chat (only sources attached to a project, via `project_sources`; empty shelf retrieves nothing)

#### 1.6.x Chat UX polish (2026-06-04)

- [x] PATCH /chats/{id} (rename + retarget scope/sources/project)
- [x] DELETE /chats/{id} and DELETE /chats/{id}/messages/{mid}
- [x] Auto-title first turn via Haiku (`anthropic_model_fast`)
- [x] Stop button + AbortSignal; persist partial assistant on client abort
- [x] Regenerate / retry last assistant turn
- [x] Markdown rendering with inline `[Pn]` citation chips + hover preview
- [x] Per-chat live scope/sources/k controls (persist via PATCH)
- [x] Citation card "+" menu: copy markdown · save to quote shelf · pin to outline node
- [x] Copy message + export thread to Markdown (Pandoc-friendly footnotes)
- [x] Follow-up question suggestions after each assistant turn
- [x] Continue affordance when stop_reason=max_tokens
- [x] Chat list polish: last-message preview, source count, relative time, inline rename, delete

### 1.7 Source viewer

- [ ] PDF viewer with PDF.js
- [ ] Jump-to-citation (open source at the right page, scroll, highlight span)
- [ ] Render non-PDF formats as styled HTML view
- [ ] Toggle: original layout view vs reflowed digital text
- [ ] Save highlight + optional note from selection

### 1.8 Library UI

- [ ] List of sources with metadata, filters, search
- [ ] Source detail page: profile, TOC, recent highlights
- [ ] Bulk operations (tag, delete) — basic only

### 1.9 Outline & evidence

- [ ] Project create / list / delete
- [x] Project source shelf UI (attach/detach library sources at `/projects/{id}/sources`; auto-attach on evidence pin)
- [ ] Outline tree editor (flat in Phase 1; hierarchical comes in Phase 2)
- [ ] "Add evidence to this node" — drag from chat result, source viewer, or quote shelf
- [ ] Evidence card displays: quote text, citation, link back to source
- [ ] Quote shelf UI

### 1.10 Export

- [x] Markdown export of outline + evidence
- [x] Citation rendering (Pandoc-friendly format with bibliography)

### 1.11 Auth

- [x] Trivial single-user auth (env-based or local password)
- [x] All queries scoped by `user_id` (hardcoded but enforced)

### 1.12 Evaluation harness

- [~] Build initial eval set: ~50 hand-graded Q→passage pairs over 5–10 books
      *(seeded with 14 entries against 3 synthetic articles; needs to grow as
      real books are ingested)*
- [x] CLI to run eval: retrieval accuracy @K, citation correctness, refusal rate
- [x] Decision rule: no retrieval/prompt change merges without running eval
      *(documented in docs/EVAL.md; CI hookup pending)*

### 1.13 Phase 1 exit checklist

- [ ] Ingest 10+ real books successfully
- [ ] Run 25 grounded queries; ≥80% return correct paragraph-level citations
- [ ] Build a real outline with attached evidence for one chapter
- [ ] Export to Markdown and review off-app

---

## Phase 2 — Writing workspace

- [x] TipTap editor with custom blocks: evidence card, citation, draft paragraph
- [x] Hierarchical outlines (parent/child tree; UI supports nesting)
- [x] Coverage map view (sections × sources matrix; gaps highlighted)
- [x] Contradiction / agreement detector across pinned evidence
- [x] Style memory: ingest user's past writing; produce a style profile prompt
      *(per-project; auto-injected into project-scoped chat system prompt)*
- [x] Versioned drafts; diff view between versions
- [x] Bibliography auto-built; CSL styles (Chicago + APA)
- [x] DOCX export via Pandoc with citations
- [x] Anti-hallucination guardrails: red-flag unsupported sentences in draft view
- [x] "Steel-man this section" pass
- [x] "What's missing" pass
- [ ] Phase 2 exit: full chapter drafted and exported using the app

---

## Phase 3 — Expand source types

- [ ] Audio ingestion (Whisper-class transcription) with timestamps
- [ ] Video ingestion (extract audio → transcribe; keep keyframes)
- [ ] Speaker diarization where useful
- [ ] YouTube ingestion (transcript + chapter markers + metadata)
- [ ] Web page ingestion (readability extraction; archive snapshot)
- [ ] Zotero sync (library + collections + attachments)
- [ ] Readwise sync (highlights → mapped to sources)
- [ ] Kindle highlights import
- [ ] Phase 3 exit: long-form piece written using mixed source types

---

## Phase 4 — Synthesis, graph & productization

### 4.1 Synthesis features

- [ ] Concept index across the library
- [ ] Cross-source comparative briefs
- [ ] Topic timelines
- [ ] Knowledge graph view (concept ↔ source ↔ outline-node)
- [ ] Question generator (Socratic prompts per chapter)
- [ ] Reading queue + spaced re-surfacing of highlights

### 4.2 Productization (only if pursuing SaaS)

- [ ] Real auth: email/OAuth, sessions, password reset, account deletion
- [ ] Multi-tenant hardening: row-level security, per-tenant rate limits
- [ ] Stripe billing: plans, usage caps, free tier, abuse detection
- [ ] Privacy policy, ToS, GDPR/CCPA, deletion guarantees, audit logs
- [ ] DMCA process; "you assert rights" upload gate
- [ ] Onboarding: empty state, sample library, tutorials, support email
- [ ] Cost metering per user; per-query and per-day caps
- [ ] Observability: metrics, logs, traces, alerting, on-call rotation
- [ ] Backups with tested restores
- [ ] Tauri desktop wrapper (folder watch, local model launch, offline)
- [ ] Mobile read-only companion (web-responsive first)

### 4.3 Phase 4 exit

- [ ] Either ship publicly with ≥1 paying user beyond ourselves, or
- [ ] Deliberately freeze productization scope and stay personal

---

## Cross-cutting / always-on

- [ ] Chat/LLM rate limiting + per-user cost caps (full design lands in Phase 4.2
      "Cost metering"; add a basic guard sooner if usage warrants)
- [ ] pg_trgm (GIN trigram) index on `chunks.text` so exact-phrase ILIKE search
      stays fast as the library grows
- [ ] Graceful 503s when MinIO/object storage is unavailable on upload
- [ ] Keep eval set up to date as new sources/queries appear
- [ ] Re-read CONCEPT.md / PHASES.md / TECHNICAL_DECISIONS.md before starting each phase
- [ ] Log every architectural revisit (when, why, what changed) in
      TECHNICAL_DECISIONS.md
- [ ] No backwards-compat shims while still pre-public
