# Evaluation harness (Phase 1.12)

This is the gate that protects retrieval and prompt quality across changes.
Every change to the retriever, the chunker, the embedder, the reranker, or
the system prompt should be tested against the eval set before merging.

## What it scores

**Retrieval (always, no API key needed):**

- **Recall@K** — for an in-scope question, did any top-K hit contain the
  expected paragraph? Matched by case-insensitive substring against the
  `expected_text_substring` of the eval entry.
- **Source-correctness@K** — did any top-K hit come from the expected source
  (`expected_source_title`)?

**Chat (optional, needs `ANTHROPIC_API_KEY`):**

- **Citation source correctness** — did the model's verified citations
  include at least one passage from the expected source?
- **Refusal correctness** on `expected: no_answer` entries — did the model
  decline rather than fabricate?

## The eval set

Lives at `backend/eval_data/eval_set.json`. Every entry has:

```jsonc
{
  "id": "flow-challenge-skill",
  "query": "What is the relationship between challenge and skill in flow?",
  "expected_source_title": "Sample Article: Flow and the Optimal Experience",
  "expected_chapter_path": ["2. The challenge–skill balance"],
  "expected_text_substring": "balance between challenge and skill"
}
```

A no-answer entry omits the expected_* fields and sets `"expected": "no_answer"`.

The repo ships a small starter set graded against three synthetic articles in
`backend/eval_data/articles/`. Replace or extend the file with entries
graded against your own library once you ingest it.

## How to run it (full walk-through)

```bash
# 1. Bring up postgres + redis + minio
make up

# 2. Apply migrations
make migrate

# 3. In one terminal, start the API
make backend-dev

# 4. In another terminal, start the ingest+embed worker
make worker

# 5. Upload the synthetic eval articles and wait for ingestion
make eval-ingest

# 6. Run the retrieval-only eval
make eval

# 7. (Optional) Run the chat-scoring eval. Requires ANTHROPIC_API_KEY in .env.
make eval-chat
```

Steps 5–7 can be re-run independently. Step 5 is idempotent (the upload
endpoint dedupes by sha256), so re-running it after a code change is safe.

## What to look for

- A clean baseline run on the synthetic articles should yield ≥ 80% on
  Recall@5 and 100% on Source@10. Anything materially worse means the
  retrieval pipeline is broken before you've even touched a real book.
- After ingesting your own books and writing entries against them, treat the
  numbers as a regression baseline: never merge a retrieval/prompt change
  that drops Recall@5 below the previous baseline.

## What the runner does NOT do

- It does not start docker-compose or the backend for you. The runner talks
  to the database via `SessionLocal`, so the database needs to be reachable
  and the chunks need to be embedded.
- It does not call the streaming chat endpoint. With `--with-chat` it
  invokes the model gateway directly with the same system prompt + user
  turn the streaming endpoint would build, then runs `verify_citations` on
  the output. This is intentional — it's faster and reproducible.

## Extending the set

Add new entries to `backend/eval_data/eval_set.json`. To grade an entry
against a real book in your library:

1. Open the source viewer and find the paragraph that answers the question.
2. Note a 5–10 word distinctive phrase from that paragraph; this becomes
   `expected_text_substring`.
3. Note the source title exactly as it appears in `/api/v1/sources`; this
   becomes `expected_source_title`.
4. Optionally note the chapter path; this is currently informational only,
   but a future scoring metric will use it.

A 30–50 entry set across 5–10 books is the Phase 1 target.
