# Research-o-Writer — Phased Roadmap

Four delivery phases, plus a Phase 0 validation step before any code is
written. Each phase has a **Goal**, a **Scope** (what's in), an explicit
**Out-of-scope** list, and an **Exit criterion** so we know when to move on.

---

## Phase 0 — Validate the value cheaply (1–2 weekends, no real code)

**Goal**: confirm the idea beats existing tools for *our* actual writing
workflow, before investing in a build.

**Scope**:
- Pick one book and one chapter we genuinely plan to write.
- Try NotebookLM, Anara, and a hand-rolled PaperQA setup against it.
- Note where each one frustrates us — that list becomes the real product spec.

**Out-of-scope**:
- Any production code.
- Any architectural decisions beyond "keep notes".

**Exit criterion**: a written list of frustrations and missing capabilities
from existing tools, mapped against the requirements in CONCEPT.md.

---

## Phase 1 — MVP: the smallest thing that beats NotebookLM for our use case

**Goal**: a usable single-user web app that lets us ingest our library,
retrieve grounded passages, and start an outline with attached evidence.

**Scope**:
- Ingest PDF, DOCX, EPUB, Markdown, plain text.
- Structure-aware chunking (chapter / section / paragraph aware).
- Hybrid retrieval (semantic + lexical) with reranker.
- Chunk metadata captured at paragraph + page granularity (see
  TECHNICAL_DECISIONS.md "Citation precision").
- Library view: list sources, show metadata, open source viewer.
- Source viewer: rendered PDF with highlight-on-citation jump.
- Grounded chat over a single source AND over the whole library, with
  clickable citations.
- Highlight + save quote → personal "quote shelf".
- One book project with a flat outline; attach evidence cards to outline
  nodes.
- Markdown export of outline + evidence.
- Single-user auth (trivial), but `user_id` on every row from day one.
- Local embeddings + reranker; Claude (Sonnet 4.6 default, Opus 4.7 for hard
  synthesis) for chat behind a model-gateway abstraction.

**Out-of-scope**:
- Audio / video / web / YouTube ingestion.
- Multi-user, billing, public signup.
- Block editor for full draft writing (basic text edit only).
- Coverage map, contradiction detector, style memory, graph view.
- Desktop app.

**Exit criterion**: we can ingest 10+ of our own books, ask grounded questions,
get correct paragraph-level citations, save quotes, build a simple outline,
attach evidence, and export it as Markdown.

---

## Phase 2 — Writing workspace

**Goal**: become the place where the book is actually written, not just
researched.

**Scope**:
- Block-based editor (TipTap/ProseMirror) with custom blocks: outline node,
  evidence card, citation, draft paragraph.
- Hierarchical outlines (book → part → chapter → section → subsection →
  paragraph stub).
- Coverage map across an outline (which sources contribute where, gaps).
- Contradiction / agreement detector across pinned evidence.
- Style memory (profile from user's past writing to tone-match suggestions).
- Versioned drafts with diff view.
- Bibliography auto-built; export to DOCX via Pandoc with citation styles
  (Chicago, APA).
- Anti-hallucination guardrails: UI flags unsupported sentences in red.
- "Steel-man this section" and "What's missing" review passes.

**Out-of-scope**:
- New source types.
- Productization (billing, multi-tenant scaling).

**Exit criterion**: we have used the app to draft and export at least one full
chapter of a real book, end-to-end, without leaving the tool.

---

## Phase 3 — Expand source types

**Goal**: bring in the rest of the world's content.

**Scope**:
- Audio / video transcription (e.g. Whisper-class) with speaker diarization
  where useful.
- YouTube ingestion (transcript + chapter markers + metadata).
- Web page ingestion (readability extraction; archive snapshot).
- Zotero sync (import library + collections).
- Readwise sync (import highlights tied to source).
- Kindle highlights import.

**Out-of-scope**:
- Live recording / podcasting.
- Browser extension (deferred; consider here or Phase 4).

**Exit criterion**: at least one full long-form piece written using a mix of
books, papers, web articles, and a podcast/lecture as sources.

---

## Phase 4 — Synthesis, graph & productization

**Goal**: deepen the reasoning surface and decide whether to open the product
to others.

**Scope (synthesis)**:
- Concept index across the library.
- Cross-source comparative briefs on demand.
- Topic timelines (how a concept evolved chronologically).
- Knowledge graph view (concept ↔ source ↔ outline-node).
- Question generator (Socratic prompts per chapter).
- Reading queue + spaced re-surfacing of highlights.

**Scope (productization, conditional)**:
- Multi-tenant hardening (already structured this way; here it gets tested).
- Billing (Stripe), plans, usage caps, free tier, abuse detection.
- Privacy policy, ToS, GDPR/CCPA, deletion guarantees.
- Onboarding, empty-state UX, sample library, tutorials.
- Tauri desktop wrapper for power users (folder-watching, local model
  launching, real offline).
- Mobile read-only companion (web-first; native if needed).

**Out-of-scope**:
- Selling to enterprise (SOC2, SSO) — only if there's pull from real users.

**Exit criterion**: either (a) we ship publicly with at least one paying user
beyond ourselves, or (b) we deliberately stay personal-only and freeze the
productization scope.

---

## Phasing principles (do not violate)

1. **Personal-first, product-ready.** Build for the builder, but pay the small
   upfront tax (multi-tenant schema, model gateway, object storage abstraction)
   that keeps the product door open.
2. **No backwards-compat shims yet.** Until Phase 4 ships externally, we are
   the only user — refactor freely.
3. **Evaluation before optimization.** Maintain a small eval set from Phase 1
   onward (~50 hand-graded questions over 5–10 real books). No retrieval or
   prompt change ships without running it.
4. **Defer features aggressively.** If a feature does not unblock writing the
   next chapter, it waits.
