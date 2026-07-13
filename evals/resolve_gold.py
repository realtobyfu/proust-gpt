#!/usr/bin/env python3
"""
Resolve gold chunks for hand-written questions.

Hand-written questions (evals/handwritten.json) are the hardest, most honest
cases — but each needs a KNOWN answering chunk before it can be scored. This
helper runs the retriever for every question whose gold_chunk_id is still
null and prints the top candidate chunks with previews, so you can eyeball
which chunk actually contains the answer and fill in gold_chunk_id by hand.

It never guesses silently: --apply-top writes the #1 reranked hit into the
file but leaves review_status="needs_check" so you must still confirm it.

Usage:
    python evals/resolve_gold.py                        # print candidates
    python evals/resolve_gold.py --file evals/handwritten.json --topk 8
    python evals/resolve_gold.py --apply-top            # prefill #1 hit (verify!)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import _bootstrap  # noqa: F401

from corpus import get_passage_text
from retrieval_adapter import ranked_indices

EVALS = Path(__file__).resolve().parent
DEFAULT_FILE = EVALS / "handwritten.json"


def preview(idx: int, n: int = 240) -> tuple[str, str]:
    p = get_passage_text(idx, lang="en")
    if not p:
        return ("(not in corpus)", "")
    text = (p.get("text", "") or "").strip().replace("\n", " ")
    return (f"{p.get('book', '?')} / {p.get('chapter', '?')}", text[:n])


def main() -> None:
    ap = argparse.ArgumentParser(description="Resolve gold chunks for hand questions")
    ap.add_argument("--file", type=Path, default=DEFAULT_FILE)
    ap.add_argument("--topk", type=int, default=8)
    ap.add_argument("--mode", default="rerank", choices=["vector", "rerank"])
    ap.add_argument("--apply-top", action="store_true",
                    help="prefill gold_chunk_id with the #1 hit (still verify!)")
    args = ap.parse_args()

    items = json.loads(args.file.read_text(encoding="utf-8"))
    unresolved = [it for it in items if it.get("gold_chunk_id") is None]
    print(f"{len(unresolved)} of {len(items)} questions need a gold chunk.\n")

    for it in unresolved:
        q = it["question"]
        ranked, _ = ranked_indices(q, depth=args.topk, mode=args.mode)
        print("=" * 78)
        print("Q:", q)
        if it.get("note"):
            print("   note:", it["note"])
        print("-" * 78)
        for rank, idx in enumerate(ranked, 1):
            loc, text = preview(idx)
            print(f"  [{rank}] #{idx:<6} {loc}")
            print(f"       {text}")
        if args.apply_top and ranked:
            it["gold_chunk_id"] = ranked[0]
            it["review_status"] = "needs_check"
        print()

    if args.apply_top:
        args.file.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Prefilled #1 hits into {args.file.name} (review_status=needs_check). VERIFY each one.")


if __name__ == "__main__":
    main()
