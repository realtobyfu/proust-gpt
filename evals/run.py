#!/usr/bin/env python3
"""
ProustGPT retrieval eval harness.

Loads a hand-reviewed gold set (question -> known answering chunk), runs one
or more retrieval configurations against the live index, and prints a
comparison table of Recall@k / MRR / latency. Results are written to
evals/results/<date>-<label>.json alongside the config that produced them, so
"I evaluated it once" becomes "the repo has an eval harness."

Usage:
    python evals/run.py                          # full grid, all questions
    python evals/run.py --single                 # baseline config only
    python evals/run.py --split test             # held-out set only (final report)
    python evals/run.py --split dev              # tuning set only
    python evals/run.py --gold evals/gold.json --depth 10
    python evals/run.py --no-write               # don't persist results JSON

Metrics are mechanical (gold chunk known), so no LLM judge is involved.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import date, datetime
from pathlib import Path

import _bootstrap  # noqa: F401

from config import config
from metrics import QueryResult, aggregate, Aggregate
from retrieval_adapter import ranked_indices, default_variants

EVALS = Path(__file__).resolve().parent
DEFAULT_GOLD = EVALS / "gold.json"
RESULTS_DIR = EVALS / "results"

KS = (1, 5, 10)


def _rel(p: Path) -> str:
    """Repo-relative display path, falling back to the absolute path."""
    try:
        return str(p.resolve().relative_to(EVALS.parent))
    except ValueError:
        return str(p)


# ── Gold set ──────────────────────────────────────────────────────────────────

def load_gold(path: Path, split: str) -> list[dict]:
    if not path.exists():
        raise SystemExit(
            f"gold set not found: {path}\n"
            "Build one first:  python evals/build_gold.py   (then hand-review it)"
        )
    items = json.loads(path.read_text(encoding="utf-8"))
    if split != "all":
        items = [it for it in items if it.get("split", "dev") == split]
    if not items:
        raise SystemExit(f"no gold questions for split={split!r} in {path}")
    return items


def gold_ids_for(item: dict) -> set:
    ids = {int(item["gold_chunk_id"])}
    for alt in item.get("accepted_alternates", []) or []:
        ids.add(int(alt))
    return ids


# ── Running one config ────────────────────────────────────────────────────────

def run_variant(gold: list[dict], variant: dict, lang: str, verbose: bool) -> Aggregate:
    label = variant["label"]
    # Drop label and any "_note"-style annotation keys; thread lang.
    kwargs = {k: v for k, v in variant.items() if k != "label" and not k.startswith("_")}
    kwargs.setdefault("lang", lang)

    results: list[QueryResult] = []
    for i, item in enumerate(gold):
        ranked, latency_ms = ranked_indices(item["question"], **kwargs)
        qr = QueryResult(
            question=item["question"],
            gold_ids=gold_ids_for(item),
            ranked=ranked,
            latency_ms=latency_ms,
            source=item.get("source", "synthetic"),
            volume=item.get("volume"),
        )
        results.append(qr)
        if verbose:
            mark = f"#{qr.hit_rank}" if qr.hit_rank else "MISS"
            print(f"  [{label}] {i + 1:>3}/{len(gold)}  {mark:>5}  {item['question'][:60]}")
    return aggregate(label, results, ks=KS)


# ── Reporting ─────────────────────────────────────────────────────────────────

def print_table(aggs: list[Aggregate]) -> None:
    print("\n" + "=" * 78)
    print("  ProustGPT Retrieval Eval  —  index:", config.PINECONE_INDEX_NAME)
    print("=" * 78)
    header = (
        f"{'config':<20} {'n':>4} {'R@1':>6} {'R@5':>6} {'R@10':>6} "
        f"{'MRR':>6} {'p50ms':>7} {'p95ms':>7} {'miss':>5}"
    )
    print(header)
    print("-" * 78)
    for a in aggs:
        print(
            f"{a.label:<20} {a.n:>4} "
            f"{a.recall.get(1, 0):>6.3f} {a.recall.get(5, 0):>6.3f} {a.recall.get(10, 0):>6.3f} "
            f"{a.mrr:>6.3f} {a.latency_p50_ms:>7.0f} {a.latency_p95_ms:>7.0f} {len(a.misses):>5}"
        )
    print("=" * 78)


def by_volume_breakdown(gold: list[dict], agg_results: dict[str, list[QueryResult]]) -> None:
    """Optional: recall@5 per volume for the baseline, to surface weak spots."""
    pass  # kept lean for v1; per-question misses are in the results JSON


def git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=EVALS, stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return None


def write_results(aggs: list[Aggregate], gold_path: Path, split: str, depth: int, label: str) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = date.today().isoformat()
    out = RESULTS_DIR / f"{stamp}-{label}.json"
    payload = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "git_commit": git_commit(),
        "gold_set": _rel(gold_path),
        "split": split,
        "depth": depth,
        "config": {
            "index": config.PINECONE_INDEX_NAME,
            "embed_model": config.COHERE_EMBED_MODEL,
            "rerank_model": config.COHERE_RERANK_MODEL,
            "retrieval_candidates": config.RETRIEVAL_CANDIDATES,
        },
        "variants": [a.as_dict() for a in aggs],
        "misses": {a.label: a.misses for a in aggs},
    }
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="ProustGPT retrieval eval harness")
    ap.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    ap.add_argument("--split", choices=["dev", "test", "all"], default="all")
    ap.add_argument("--depth", type=int, default=10, help="ranked depth (>= max k)")
    ap.add_argument("--lang", default="en", help="Pinecone namespace")
    ap.add_argument("--single", action="store_true", help="baseline config only")
    ap.add_argument("--variants", type=Path, default=None,
                    help="JSON file of custom variants (replaces the default grid); "
                         "each item may set index_name/embed_model for alt-index runs")
    ap.add_argument("--label", default=None, help="results filename label")
    ap.add_argument("--no-write", action="store_true", help="skip writing results JSON")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    if args.depth < max(KS):
        raise SystemExit(f"--depth must be >= {max(KS)} to score Recall@{max(KS)}")

    gold = load_gold(args.gold, args.split)

    if args.variants:
        variants = json.loads(args.variants.read_text(encoding="utf-8"))
        for v in variants:
            v.setdefault("depth", args.depth)
            if v["depth"] < max(KS):
                raise SystemExit(f"variant {v['label']!r} depth {v['depth']} < {max(KS)}")
    else:
        variants = default_variants(depth=args.depth)
        if args.single:
            variants = [v for v in variants if "baseline" in v["label"]]

    print(f"Gold: {len(gold)} questions (split={args.split})  |  depth={args.depth}  |  variants={len(variants)}")
    aggs = []
    for v in variants:
        try:
            aggs.append(run_variant(gold, v, args.lang, args.verbose))
        except Exception as e:  # a bad index/model shouldn't kill the whole grid
            print(f"  ✗ variant {v['label']!r} failed: {type(e).__name__}: {e}")

    if not aggs:
        raise SystemExit("no variants produced results (all failed?)")

    print_table(aggs)

    if not args.no_write:
        label = args.label or f"{args.split}-depth{args.depth}"
        out = write_results(aggs, args.gold, args.split, args.depth, label)
        print(f"\nResults written to {_rel(out)}")


if __name__ == "__main__":
    main()
