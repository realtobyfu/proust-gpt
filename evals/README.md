# ProustGPT retrieval eval

A gold-set harness for measuring retrieval quality on the Proust corpus. Every
question has a **known answering chunk**, so retrieval is scored mechanically —
no LLM judge, no "who judges the judge?" validity problem.

```
Recall@1 / @5 / @10   is the gold chunk in the top k?
MRR                   mean reciprocal rank of the gold chunk
Latency p50 / p95     end-to-end retrieval, across the whole set (not one query)
```

## Files

| File | What it is |
|------|-----------|
| `gold.json` | The reviewed gold set. **The credible artifact.** Committed. |
| `handwritten.json` | Hard reader-written questions (the honest cases). |
| `gold_candidates.json` | LLM-generated candidates, pre-review. Not the gold set. |
| `results/YYYY-MM-DD-*.json` | Dated results + the config that produced them. Committed. |
| `build_gold.py` | Sample chunks → generate anti-leakage questions → candidates. |
| `resolve_gold.py` | Find the gold chunk for a hand-written question. |
| `review_gold.py` | LLM triage (optional) + promote keepers → `gold.json`. |
| `run.py` | The harness: score configs, print the table, write results. |
| `metrics.py` / `retrieval_adapter.py` | Pure metrics; the seam to the live pipeline. |
| `test_metrics.py` | Unit tests for the metrics (no network). |

## Build the gold set (one time, ~half a day of review)

```bash
# from repo root, with the backend venv active:
source backend/venv/bin/activate

# 1. Generate ~120 candidates, stratified across the 7 volumes.
python evals/build_gold.py            # -> evals/gold_candidates.json

# 2. (optional) LLM triage to pre-flag weak questions — an AID, not the review.
python evals/review_gold.py --triage

# 3. HAND-REVIEW gold_candidates.json. This pass is the actual work and the
#    actual credibility. For each question set "review_status": "keep" or
#    "reject". Delete/reject anything unanswerable, ambiguous, or answerable
#    by many passages. Expect to keep ~80–100.
#      - Flagged "leakage" (question reuses passage wording) → reject or reword.
#      - To hold out a test set, set "split": "test" on ~30 you won't tune on.

# 4. Give the hand-written questions a gold chunk.
python evals/resolve_gold.py          # prints top hits; fill in gold_chunk_id
#   (or --apply-top to prefill the #1 hit, then VERIFY each — it marks them
#    review_status="needs_check" on purpose.)

# 5. Assemble the gold set from the keepers.
python evals/review_gold.py --promote # -> evals/gold.json
```

## Run the harness

```bash
python evals/run.py                 # full variant grid, all questions
python evals/run.py --single        # deployed baseline config only
python evals/run.py --split test    # held-out set — the number you report
python evals/run.py --split dev     # tuning set — iterate here
python evals/run.py -v              # per-question hit rank / MISS
```

Output is a comparison table and a dated JSON in `results/` recording the
metrics, the per-config miss list, and a config snapshot (index, embedding
model, rerank model, candidate pool).

### The variant grid

The default grid runs against the current index with **no re-ingest**:

- `vector-only` — pure Pinecone vector search
- `rerank (baseline)` — vector pool → Cohere `rerank-v3.5` (mirrors production)
- `rerank-pool50` — same, wider candidate pool

### Custom variants (`--variants`) — alternate index / embedding model

Pass a JSON grid to compare configs beyond the defaults. Each variant may set
`index_name` and `embed_model` to point at a *different* Pinecone index and
embed queries with a different Cohere model. See `variants.example.json`.

```bash
python evals/run.py --variants evals/variants.example.json
```

A variant that references a missing index fails on its own (clear 404) without
killing the rest of the grid.

**Embedding-model swap — gold-compatible.** Same chunks, new vectors. Build the
alternate index once, then point a variant at it:

```bash
# re-ingest the SAME chunks with a different embedding model into a new index
cd backend
COHERE_EMBED_MODEL=embed-english-v3.0 python scripts/ingest_pinecone.py \
    --index proust-index-v3-en3        # dimension must match the new model
```

Your `gold_chunk_id`s stay valid because the chunk `index` ids are unchanged.

**Chunk-size swap — needs gold re-mapping.** A different chunk size produces new
boundaries → new `index` ids → your v3 `gold_chunk_id` points at nothing
meaningful. To evaluate it honestly you must re-map the gold set to the new
chunks: for each gold question, find the new chunk whose text contains the old
gold chunk's answer span (highest text overlap) and use *that* id. Score
against the remapped gold. The adapter can point at the re-chunked index, but
the numbers are meaningless against un-remapped v3 gold — don't trust them.

Also future work: an LLM-judge pass for graded multi-passage relevance (when
several passages are partially relevant rather than one being *the* answer).

## gold.json schema

```json
{
  "question": "What pastry, dipped in tea, unlocks the narrator's memory of Combray?",
  "gold_chunk_id": 196,
  "accepted_alternates": [188],        // optional: near-duplicate chunks that also answer
  "volume": 1,
  "book": "Swann's Way",
  "chapter": "Overture",
  "source": "synthetic",               // or "hand"
  "split": "dev"                       // or "test" (held out)
}
```

`gold_chunk_id` is a passage's `index` field (Pinecone id `passage-{index}`).
Near-duplicate passages are common in Proust — when two chunks both contain the
answer, list the extras in `accepted_alternates` so either counts as a hit.

## Keeping the numbers honest

- **Don't tune and report on the same questions.** Iterate on `--split dev`;
  report `--split test`, which you only run at the end.
- **Report the number you get.** "Started at 61%, found chunking split scenes
  mid-sentence, got to 78%" is a better story than a flat 92% — it shows the
  loop. Negative findings included.
- **Near-duplicates:** use `accepted_alternates` so a correct-but-different
  chunk isn't scored as a miss.
- **Leakage:** if a question reuses the passage's distinctive wording, vector
  search finds it trivially and the score is fake-high. `build_gold.py` flags
  4+ word overlaps; reject or reword them in review.

## Note: app generation model

The eval harness scores **retrieval only** and does not call the app's LLM.

Separately: the app was configured for `moonshotai/kimi-k2-instruct`, which
Groq has since **retired (404)**. `LLM_MODEL_NAME` is now
`llama-3.3-70b-versatile` (in `backend/.env` and the `config.py` default);
smoke-tested end-to-end on the RAG answer path. Gold generation uses the same
model (override with `--model`).
