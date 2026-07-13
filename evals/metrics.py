"""
Retrieval metrics for the ProustGPT eval harness.

Every gold question has a KNOWN answering chunk (plus optional accepted
alternates for near-duplicate passages). That means we can score retrieval
mechanically — no LLM judge required:

  * Recall@k  — is a gold chunk in the top k retrieved?  (reported at k=1,5,10)
  * MRR       — mean reciprocal rank of the first gold hit
  * Latency   — p50 / p95 of end-to-end retrieval, across the whole set

These are pure functions over already-retrieved rankings, so they are fast,
deterministic, and unit-testable without touching the network.
"""
from __future__ import annotations

from dataclasses import dataclass, field


def _first_hit_rank(ranked: list, gold_ids: set) -> int | None:
    """1-based rank of the first ranked id that is in gold_ids, else None."""
    for i, cid in enumerate(ranked):
        if cid in gold_ids:
            return i + 1
    return None


def recall_at_k(ranked: list, gold_ids: set, k: int) -> float:
    """1.0 if any gold id appears in the top k of `ranked`, else 0.0."""
    return 1.0 if any(cid in gold_ids for cid in ranked[:k]) else 0.0


def reciprocal_rank(ranked: list, gold_ids: set) -> float:
    """1 / rank of the first gold hit; 0.0 if no gold id is in `ranked`."""
    rank = _first_hit_rank(ranked, gold_ids)
    return 1.0 / rank if rank else 0.0


def percentile(values: list[float], p: float) -> float:
    """Linear-interpolation percentile (p in [0, 100]). Empty -> 0.0."""
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    rank = (p / 100.0) * (len(s) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(s) - 1)
    frac = rank - lo
    return s[lo] + (s[hi] - s[lo]) * frac


@dataclass
class QueryResult:
    """Per-question retrieval outcome."""
    question: str
    gold_ids: set
    ranked: list
    latency_ms: float
    source: str = "synthetic"
    volume: int | None = None
    hit_rank: int | None = field(default=None)

    def __post_init__(self):
        self.hit_rank = _first_hit_rank(self.ranked, self.gold_ids)


@dataclass
class Aggregate:
    """Aggregate scores for one retrieval configuration over a gold set."""
    label: str
    n: int
    recall: dict[int, float]        # k -> recall@k
    mrr: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_mean_ms: float
    misses: list[str]              # questions where no gold chunk was retrieved

    def as_dict(self) -> dict:
        return {
            "label": self.label,
            "n": self.n,
            "recall": {str(k): round(v, 4) for k, v in self.recall.items()},
            "mrr": round(self.mrr, 4),
            "latency_p50_ms": round(self.latency_p50_ms, 1),
            "latency_p95_ms": round(self.latency_p95_ms, 1),
            "latency_mean_ms": round(self.latency_mean_ms, 1),
            "num_misses": len(self.misses),
        }


def aggregate(label: str, results: list[QueryResult], ks=(1, 5, 10)) -> Aggregate:
    """Roll per-query results up into recall@k, MRR, and latency percentiles."""
    n = len(results)
    if n == 0:
        return Aggregate(label, 0, {k: 0.0 for k in ks}, 0.0, 0.0, 0.0, 0.0, [])

    recall = {
        k: sum(recall_at_k(r.ranked, r.gold_ids, k) for r in results) / n
        for k in ks
    }
    mrr = sum(reciprocal_rank(r.ranked, r.gold_ids) for r in results) / n
    latencies = [r.latency_ms for r in results]
    misses = [r.question for r in results if r.hit_rank is None]

    return Aggregate(
        label=label,
        n=n,
        recall=recall,
        mrr=mrr,
        latency_p50_ms=percentile(latencies, 50),
        latency_p95_ms=percentile(latencies, 95),
        latency_mean_ms=sum(latencies) / n,
        misses=misses,
    )
