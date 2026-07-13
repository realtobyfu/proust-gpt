"""
Retrieval adapter — turns a query into a ranked list of chunk ids.

The harness scores rankings, so it only needs the *order* of chunk ids a
retriever returns, not the stitched/formatted passages the app serves. This
module exposes that ordering for two configurations that require no
re-ingestion (so they run against the live index today):

  * "vector"  — pure Pinecone vector search (embed-v4.0), top `depth`
  * "rerank"  — fetch `candidates` from Pinecone, then Cohere rerank-v3.5,
                keep top `depth`

A chunk id is the passage's `index` metadata field (Pinecone id
`passage-{index}`), matching how gold chunks are identified in gold.json.

Embedding-model / alternate-index variants (Step 3+): a variant may point at a
different Pinecone `index_name` and embed queries with a different Cohere
`embed_model`. This is gold-COMPATIBLE only when the alternate index holds the
SAME chunks (same `index` ids) — i.e. an embedding-model swap. A different
CHUNK SIZE produces new `index` ids and invalidates gold_chunk_id; that path
needs gold re-mapping (see README) and is not something this adapter can paper
over. Building the alternate index is a one-time `ingest_pinecone.py` run.
"""
from __future__ import annotations

import time

import _bootstrap  # noqa: F401  (path + .env side effects)

from config import config
from retrieval import _pinecone_query, get_pinecone_client
from langchain_cohere import CohereRerank, CohereEmbeddings
from langchain_core.documents import Document


# Cache rerankers by top_n so we don't rebuild the client per query.
_rerankers: dict[int, CohereRerank] = {}


def _reranker(top_n: int) -> CohereRerank:
    if top_n not in _rerankers:
        _rerankers[top_n] = CohereRerank(
            model=config.COHERE_RERANK_MODEL,
            cohere_api_key=config.COHERE_API_KEY,
            top_n=top_n,
        )
    return _rerankers[top_n]


def _indices(docs) -> list[int]:
    out = []
    for d in docs:
        idx = d.metadata.get("index")
        if idx is not None:
            out.append(int(idx))
    return out


# ── Alternate index / embedding model (for embed-model variants) ──────────────
# Caches keyed by name/model so we build one client each, not one per query.
_indexes: dict[str, object] = {}
_embedders: dict[str, CohereEmbeddings] = {}


def _index_handle(name: str):
    if name not in _indexes:
        _indexes[name] = get_pinecone_client().Index(name)
    return _indexes[name]


def _embedder(model: str) -> CohereEmbeddings:
    if model not in _embedders:
        _embedders[model] = CohereEmbeddings(model=model, cohere_api_key=config.COHERE_API_KEY)
    return _embedders[model]


def _query_docs(query: str, top_k: int, lang: str, index_name: str, embed_model: str) -> list[Document]:
    """Vector query against an arbitrary index/embed model.

    Returns Documents with page_content = passage text (for reranking) and
    metadata carrying the `index` field (for scoring). Mirrors production
    ranking; used only when a variant overrides index_name or embed_model.
    """
    vec = _embedder(embed_model).embed_query(query)
    res = _index_handle(index_name).query(
        vector=vec, top_k=top_k, include_metadata=True, namespace=lang,
    )
    docs = []
    for m in res.matches:
        md = dict(m.metadata or {})
        text = md.get("text_fr") if (lang == "fr" and md.get("text_fr")) else md.get("text", "")
        docs.append(Document(page_content=text or "", metadata=md))
    return docs


def _vector_docs(query: str, top_k: int, lang: str, index_name: str | None, embed_model: str | None):
    """Production path when no overrides; parameterized path otherwise."""
    if index_name is None and embed_model is None:
        return _pinecone_query(query, top_k=top_k, lang=lang)
    return _query_docs(
        query, top_k, lang,
        index_name or config.PINECONE_INDEX_NAME,
        embed_model or config.COHERE_EMBED_MODEL,
    )


def ranked_indices(
    query: str,
    depth: int = 10,
    mode: str = "rerank",
    lang: str = "en",
    candidates: int | None = None,
    index_name: str | None = None,
    embed_model: str | None = None,
) -> tuple[list[int], float]:
    """Return (ranked chunk ids, latency_ms) for one query.

    Args:
        query:       the reader's question
        depth:       how many ranked ids to return (>= max k you score)
        mode:        "vector" or "rerank"
        lang:        Pinecone namespace ("en" / "fr")
        candidates:  vector-search pool size before reranking
                     (defaults to config.RETRIEVAL_CANDIDATES; forced >= depth)
        index_name:  alternate Pinecone index (embedding-model variants).
                     Must hold the same chunk ids as gold, or scores are moot.
        embed_model: alternate Cohere embed model for the query vector.

    Latency is wall-clock for the retrieval work only — no LLM generation —
    which is the number the "50ms" claim needs to be replaced by.
    """
    pool = candidates or config.RETRIEVAL_CANDIDATES

    start = time.perf_counter()
    if mode == "vector":
        docs = _vector_docs(query, depth, lang, index_name, embed_model)
        ranked = _indices(docs)
    elif mode == "rerank":
        pool = max(pool, depth)
        cand_docs = _vector_docs(query, pool, lang, index_name, embed_model)
        reranked = _reranker(depth).compress_documents(cand_docs, query)
        ranked = _indices(reranked)
    else:
        raise ValueError(f"unknown retrieval mode: {mode!r}")
    latency_ms = (time.perf_counter() - start) * 1000.0

    return ranked, latency_ms


# ── Variant grid ──────────────────────────────────────────────────────────────
# Each variant is a label + kwargs for ranked_indices(). The baseline mirrors
# the deployed config (rerank over a 30-candidate pool). Everything here runs
# against the current index with no re-ingest.

def default_variants(depth: int = 10) -> list[dict]:
    return [
        {"label": "vector-only", "mode": "vector", "depth": depth},
        {
            "label": "rerank (baseline)",
            "mode": "rerank",
            "depth": depth,
            "candidates": config.RETRIEVAL_CANDIDATES,
        },
        {"label": "rerank-pool50", "mode": "rerank", "depth": depth, "candidates": 50},
    ]
