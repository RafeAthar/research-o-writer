# Research-o-Writer — Technical Decisions

A record of the architectural choices made during planning, with rationale,
so we can revisit them deliberately rather than by drift.

---

## 1. Personal-first, product-ready

**Decision**: Build the personal tool first; pay a small upfront tax to keep
the product door open.

**Why**: The two paths (personal vs SaaS) diverge fast (auth, billing,
copyright, multi-tenant scale, support, compliance). Trying to build the
product version on day one is expensive; locking ourselves into a
personal-only design is also expensive to undo later.

**Concrete rules from day one**:

- Every database row carries `user_id` (hardcoded to the builder's id while
  single-user).
- Postgres + pgvector instead of a local file index (same code path scales).
- All LLM calls go through a thin **model gateway** (swap/meter/observe in
  one place).
- File originals live in object storage (local MinIO now, R2/S3 later).
- No user preferences hard-coded; even single-user settings are per-user rows.
- Costs and abuse considerations stay on the radar but unsolved until Phase 4.

**Revisit when**: starting Phase 4 productization.

---

## 2. LLM strategy: hybrid (local embeddings + Claude for synthesis)

**Decision**:
- **Embeddings**: local (BGE-M3 or Qwen3-Embedding-class).
- **Reranker**: local (cross-encoder, ~500M params).
- **Chat / synthesis LLM**: Claude — Sonnet 4.6 default, Opus 4.7 for heavy
  synthesis tasks.

**Why**:
- Embeddings/reranker run fine on CPU at our scale, are computed once per
  chunk, and avoid sending full books to the cloud.
- Chat/synthesis is where quality matters most for grounded answers and
  long-form writing; Claude is the strongest available and the cost is bounded
  per query.
- Hybrid sweet spot for 16–32 GB machines: heavy work stays free locally; the
  smart work goes to the cloud.
- Keeps the door open for an "all-local" privacy mode by swapping just the
  LLM gateway implementation.

**Hardware budget for local components**:
- Embeddings + reranker: 8 GB RAM, CPU OK, GPU optional.
- (No local chat LLM in Phase 1 — would require 16–32+ GB and a GPU for
  acceptable speed.)

**Revisit when**: Claude pricing changes materially, or we need a privacy
mode for sensitive sources.

---

## 3. Library scale: design for ~100 books, headroom to 1,000

**Decision**: Treat ~50–100 books as the target; design choices must remain
correct up to ~1,000 books with no rearchitecture.

**Numbers**:
- A non-fiction book ≈ 80–120K words ≈ ~150K tokens.
- At ~500-token chunks → ~300–400 chunks per book.
- 100 books × 400 chunks = ~40,000 chunks. Trivial scale.

**Implications**:
- **Vector DB**: pgvector with HNSW index. No need for Qdrant/Weaviate/Pinecone.
- **Lexical search**: Postgres FTS. No need for Elasticsearch/OpenSearch/
  Meilisearch.
- **Embedding cost**: negligible — minutes on GPU, hours on CPU, one-time.
- **No need** for sharding, hierarchical indexes, or summary-then-drill
  retrieval tricks.
- **We can afford** to store multiple representations per chunk (raw text +
  summary + extracted concepts) and search across all of them.

**Scale revisit thresholds**:
- ~1,000 books: still pgvector; consider per-source pre-filtering for latency.
- ~10,000 books: dedicated vector DB; hierarchical retrieval (find books
  first, then chunks within them).
- ~100,000+ books: a different product.

---

## 4. Citation precision

**Decision**: Target **paragraph-level** citations; gracefully fall back to
page-level when source extraction quality is poor.

**Tiers**:

| Tier | Looks like | Required data |
|---|---|---|
| Source-level | "From *Flow* by Csikszentmihalyi" | source_id |
| Section/chapter | "*Flow*, Ch. 4, 'Conditions of Flow'" | + chapter_path |
| Page | "*Flow*, Ch. 4, p. 72" | + page_start/page_end |
| Paragraph | "*Flow*, Ch. 4, p. 72, ¶3, beginning 'When attention…'" | + paragraph_index + opening words |
| Sentence/span | "*Flow*, Ch. 4, p. 72, lines 14–18" | + char_start/char_end |

**Each chunk record stores all of**: `source_id, chapter_path, page_start,
page_end, paragraph_index, char_start, char_end, text`.

**Why store everything**: storing extra metadata is cheap; reconstructing it
from an already-chunked corpus is painful.

**UI rule**: degrade gracefully — show "Ch. 4, p. 72" when paragraph-level is
not trustworthy (e.g. bad OCR), without lying about precision.

---

## 5. Output formats

**Decision**: Markdown + DOCX export in Phase 1. LaTeX/EPUB/HTML come for free
later via Pandoc.

**Why**: matches the user's existing writing workflow; Pandoc handles all of
them with one toolchain; CSL bibliography files give standard citation
styles (Chicago, APA, etc.).

---

## 6. Frontend shell: web-first, Tauri desktop wrapper later

**Decision**: Build a normal web app (Next.js/React); add a **Tauri** desktop
wrapper in Phase 4 if folder-watching, local model launching, or real offline
turn out to matter.

**Why**:
- Web is where the "try it" funnel lives if this becomes a product.
- 100 books is small enough that browser performance is fine.
- Tauri wraps the same web app in a native shell with full filesystem access
  for ~10% extra effort and a small binary, vs Electron's heavier footprint.
- Building desktop-first locks out the product path significantly.

**What we lose by being web-first in Phase 1**: auto-watching a folder of
books and ingesting new ones without manual upload. Acceptable for now.

---

## 7. Recommended Phase 1 stack

| Layer | Choice |
|---|---|
| Backend language/framework | Python + FastAPI |
| Database | Postgres + pgvector (HNSW index) |
| Lexical search | Postgres full-text search |
| Object storage | S3-compatible — MinIO locally → R2/S3 if productized |
| Background jobs | RQ or Celery (start with RQ for simplicity) |
| Embeddings | Local: BGE-M3 (or Qwen3-Embedding) |
| Reranker | Local: cross-encoder (~500M params) |
| Chat/synthesis | Claude (Sonnet 4.6 default; Opus 4.7 for hard synthesis) via a model-gateway abstraction |
| Frontend framework | Next.js + React + TypeScript |
| Editor | TipTap (ProseMirror) — even Phase 1 wants block-based |
| PDF rendering | PDF.js |
| Document conversion | Pandoc |
| Auth | Trivial in Phase 1; schema multi-tenant from day one |

---

## 8. Ingestion pipeline (Phase 1)

**Parsers**:
- PDF: PyMuPDF / pdfplumber for born-digital text + structure; consider
  Marker or LlamaParse for tricky layouts; Tesseract / docTR fallback for
  scanned books.
- DOCX: `python-docx`.
- EPUB: `ebooklib`.
- HTML: `readability` + `beautifulsoup4`.
- Markdown / TXT: direct read.

**Steps**:
1. Detect format and parse to a structural tree (headings → sections →
   paragraphs).
2. Run OCR fallback for scanned PDFs.
3. Enrich metadata via ISBN/DOI lookup (OpenLibrary, CrossRef, Google Books).
4. Extract and store TOC.
5. **Structure-aware chunking**: ~300–800 tokens per chunk, never crossing a
   heading boundary, with overlap. Each chunk records all citation-precision
   fields from §4.
6. Compute embeddings for each chunk; insert into pgvector with HNSW.
7. Insert chunks into Postgres FTS index for lexical search.
8. Generate per-source profile (topics, key concepts per chapter, abstract)
   via Claude — cached.

**Storage layout**:
- Original file → object storage.
- Extracted JSON tree (structure + paragraphs) → object storage.
- Chunks + embeddings + metadata → Postgres.

---

## 9. Retrieval pipeline (Phase 1)

1. Parse query intent (free text → optional filters: source, chapter, tag).
2. Run **semantic** search (pgvector) → top K1 (e.g. 50).
3. Run **lexical** search (FTS / phrase) → top K2 (e.g. 50).
4. Merge + dedupe.
5. **Rerank** with cross-encoder → top K3 (e.g. 10).
6. Return chunks with full citation metadata.
7. For chat: feed chunks to Claude with strict prompt: cite each claim;
   refuse if support is weak; mark extractive vs synthetic responses.
8. Post-process: verify every citation in the answer resolves to a real
   chunk id; reject/regenerate otherwise.

---

## 10. Evaluation

**Decision**: maintain a small eval set from Phase 1 onward. ~50 hand-graded
questions over 5–10 real books, with the "right passage" labelled.

**Why**: without it, we can't tell whether changes to chunking / retrieval /
prompts help or hurt. Eval costs an afternoon to build and pays off forever.

**No retrieval or prompt change ships without running the eval.**

---

## 11. Open questions / explicit deferrals

- **Citation style coverage**: which CSL styles do we support in Phase 2
  beyond Chicago and APA?
- **Quote-of-the-day / spaced re-surfacing UX**: notification channel
  (email? in-app?) — defer to Phase 4.
- **Collaboration**: multiple authors on one project — not in scope through
  Phase 4 unless real demand appears.
- **Mobile**: Phase 4 only; web-responsive UI in the meantime.
- **Voice input for queries**: Phase 3+, after audio ingestion is in.
