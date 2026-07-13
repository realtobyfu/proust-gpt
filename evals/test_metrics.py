"""
Unit tests for the retrieval metrics (pure, no network).

Run:  cd evals && python -m pytest test_metrics.py -q
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from metrics import (  # noqa: E402
    recall_at_k,
    reciprocal_rank,
    percentile,
    aggregate,
    QueryResult,
)


def test_recall_at_k_boundaries():
    ranked = [9, 4, 7, 1, 3]
    gold = {7}  # rank 3
    assert recall_at_k(ranked, gold, 1) == 0.0
    assert recall_at_k(ranked, gold, 2) == 0.0
    assert recall_at_k(ranked, gold, 3) == 1.0
    assert recall_at_k(ranked, gold, 10) == 1.0


def test_recall_miss():
    assert recall_at_k([1, 2, 3], {99}, 3) == 0.0


def test_reciprocal_rank():
    assert reciprocal_rank([9, 4, 7], {7}) == 1 / 3
    assert reciprocal_rank([7, 4, 9], {7}) == 1.0
    assert reciprocal_rank([1, 2, 3], {99}) == 0.0


def test_accepted_alternates_count_as_hit():
    # A near-duplicate passage in gold_ids should also count.
    ranked = [5, 8, 2]
    assert recall_at_k(ranked, {8, 2}, 2) == 1.0  # rank-2 alternate found
    qr = QueryResult("q", {8, 2}, ranked, 1.0)
    assert qr.hit_rank == 2


def test_percentile_interpolation():
    assert percentile([10, 20, 30, 40], 50) == 25.0
    assert percentile([10, 20, 30, 40], 0) == 10.0
    assert percentile([10, 20, 30, 40], 100) == 40.0
    assert percentile([5], 95) == 5
    assert percentile([], 50) == 0.0


def test_aggregate():
    results = [
        QueryResult("a", {9}, [9, 1, 2], 5.0),   # hit @1
        QueryResult("b", {2}, [1, 3, 2], 7.0),   # hit @3
        QueryResult("c", {8}, [1, 3, 4], 9.0),   # miss
    ]
    agg = aggregate("t", results, ks=(1, 5, 10))
    assert agg.n == 3
    assert agg.recall[1] == 1 / 3       # only "a" hits at k=1
    assert agg.recall[5] == 2 / 3       # a and b within top 5
    assert abs(agg.mrr - (1.0 + 1 / 3 + 0.0) / 3) < 1e-9
    assert agg.misses == ["c"]
    assert agg.latency_p50_ms == 7.0
