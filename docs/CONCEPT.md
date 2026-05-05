# Research-o-Writer — Concept & Vision

## 1. One-line summary

A personal, source-grounded research and writing workspace where every claim,
idea, or paragraph in a book/article can be traced back to specific passages in
the user's own library of books, papers, and (later) audio/video/web sources —
with both semantic and exact search, and a chat interface that never invents
references.

## 2. The problem being solved

The user is planning to write books and long-form articles on areas they want
to study deeply (creativity, addiction, etc.). The current pain points:

- Reading many books on a topic, but losing track of which concept lives in
  which book.
- When building an outline, it is hard to know which book / section / page
  contributes to which subsection of the planned writing.
- Physical and even digital books are not handy for cross-source search.
- Existing tools either chat with one PDF, or organize references, or assist
  writing — none combine all three with strict source-grounding and
  outline-driven authoring.

## 3. Two user-modes (named explicitly)

Both modes are bundled in one product but should be designed as distinct
surfaces.

- **Researcher mode**: explore a topic across many sources, compare how
  different authors treat it, harvest quotes, build a personal concept index.
- **Writer mode**: build a hierarchical outline and draft sections where each
  subsection is fed by specific evidence pinned from sources.

## 4. Core requirements

### A. Source ingestion

- Phase 1 formats: PDF, DOCX, EPUB, Markdown, plain text, HTML.
- Phase 2 formats: audio/video (transcribe), web URLs, YouTube.
- Phase 3 formats: live feeds (RSS, Substack, Kindle highlights, Zotero sync).
- Per source: preserve original layout (page numbers, headings, footnotes,
  figures/captions) AND produce a clean reflowed digital text.
- Auto-extract metadata: title, author, year, publisher, ISBN/DOI, table of
  contents, chapter/section structure.
- Auto-generate a **source profile**: what topics it covers, density per topic,
  key concepts per chapter/page range, reading level, length.

### B. Indexing & retrieval

- **Hybrid search**: semantic (embeddings) + lexical (BM25/FTS) + exact phrase.
  Both matter — `"problem reversal"` needs exact match; "techniques for
  breaking mental fixedness" needs semantic.
- Chunking is **structure-aware** (chapter → section → paragraph), not just
  fixed token windows, so citations resolve to meaningful units.
- Every chunk carries: source ID, chapter path, page range, paragraph index,
  character offsets — so any answer can render a precise citation.
- Re-ranking layer on top of retrieval for quality.

### C. Grounded chat / Q&A

- Answers must cite passages with clickable references that open the source at
  the right page/paragraph with the relevant span highlighted.
- Mode toggle: *single-source* (chat with one book) vs *multi-source* (whole
  library) vs *scoped* (this outline / this project).
- Mandatory "no source = no claim" — if retrieval returns nothing strong, the
  model says so rather than improvising.
- Comparison queries: "How do Csikszentmihalyi and De Bono differ on
  incubation?" → side-by-side grounded answer.

### D. Outline-driven writing (the core differentiator)

- Hierarchical outline (book → part → chapter → section → subsection →
  paragraph stub).
- For each node, attach **evidence cards** — pinned quotes/passages from
  sources with citations.
- "Fill this section": retrieval scoped to the topic of the node, ranked by
  which sources cover it most.
- "Coverage map": across the outline, which sources contribute where, and
  which sections are under-evidenced.
- Draft view that interleaves prose with footnotes/sidebar showing supporting
  passages live.
- Export to Markdown / DOCX (LaTeX later) with footnotes or in-text citations
  in standard styles (Chicago, APA, etc.).

### E. Knowledge accumulation

- Highlights & notes per source, persisted across sessions.
- Personal **concept index**: e.g. "creativity → problem reversal" lists every
  passage collected on it across all books, plus user notes.
- Tags/topics that span sources.
- Optional graph view: concept ↔ source ↔ outline-node.

## 5. Additional features worth adding

1. **Per-source synthesis**: auto-generated chapter summaries, key claims,
   glossary, and a "what this book argues" abstract.
2. **Cross-source synthesis on demand**: pick N sources + a topic → comparative
   brief with quotes.
3. **Contradiction / agreement detector**: surface where sources disagree on a
   concept.
4. **Quote shelf**: clip-and-save passages with one click; reusable across
   outlines/books.
5. **Question generator**: Socratic questions per chapter to deepen
   understanding.
6. **Anti-hallucination guardrails**: every model claim links to a chunk; UI
   flags any unsupported sentence.
7. **Versioned drafts** with diff view.
8. **Style memory**: a profile of the user's voice from past writing so AI
   suggestions match tone.
9. **Reading queue & spaced re-surfacing** of saved highlights (Readwise-style)
   — directly addresses "remember which book had what".
10. **Citation hygiene**: bibliography auto-built; duplicate-detection across
    editions; DOI/ISBN auto-lookup.
11. **Privacy mode**: local-only embeddings/inference option for sensitive or
    copyrighted material.
12. **Audio companion**: text-to-speech for any source or the user's draft.
13. **Topic timeline**: how a concept evolved chronologically across sources.
14. **"Steel-man this section"** and **"What's missing"** review passes over
    the draft.

## 6. Existing tools and gaps

| Tool | What it does | Gap for our use case |
|---|---|---|
| NotebookLM (Google) | Upload sources, grounded chat, briefings, audio overviews | No outline-driven writing; weak structure-aware citations; library-size limits; no exact/keyword search; no manuscript export; no offline/local |
| Anara / SciSpace | Chat with research papers | Built for academic papers, not books; weak long-form writing surface |
| Elicit | Research question → paper findings table | Empirical lit reviews only; not a writing tool |
| Humata / ChatPDF / AskYourPDF | Chat with a PDF | Single-doc; shallow citations; no outline/writing |
| Perplexity / You.com | AI search over the web | Not a private library |
| Scholarcy | Auto-summarize papers | No chat, no library workspace |
| ResearchRabbit / Connected Papers / Litmaps | Citation graph exploration | Discovery only |
| Mendeley / Zotero | Reference managers + PDF reader | No semantic search, no chat, no writing surface |
| Readwise Reader | Read-later + highlights + AI ghostreader | Consumption + recall, not authoring |
| Recall | Auto-organize summaries into a knowledge graph | Light on grounded chat and writing |
| Mem / Reflect / Heptabase | PKM with AI | Notes-first; sources aren't first-class |
| Obsidian + Smart Connections / Copilot | Local notes with embeddings | DIY; manual ingestion |
| Sudowrite / Lex / Granola | AI writing assistants | Generative-first, not source-grounded |
| Scrivener | Long-form manuscript organizer | No AI, no retrieval |
| MarginNote / LiquidText | PDF annotation + mind-mapping | Single-device, no cross-source AI |
| Khoj | Personal AI over your files (open source) | Closest in spirit; lacks polished writing/outline UX |
| PaperQA | RAG over scientific PDFs with strong citations | Library, not product; no writing surface |

**The gap we are filling**: a workspace that treats the user's *private
library* as the substrate, gives *book-grade citations* (chapter + page +
paragraph), and binds retrieval to an *outline being actively written into*.
NotebookLM + Scrivener + Readwise mashed together, with stronger citation
discipline.

## 7. Audience strategy

- Primary user: the builder themselves (writing books on creativity, addiction,
  etc.).
- Secondary, eventual: independent researchers, non-fiction authors,
  journalists, graduate students, and lifelong learners with personal libraries.
- Build the personal tool first, but make architectural choices that don't
  slam the door on the product version (see TECHNICAL_DECISIONS.md §
  "Personal-first, product-ready").
