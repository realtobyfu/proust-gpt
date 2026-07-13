#!/usr/bin/env python3
"""
Review helper: triage candidates, then promote the keepers to gold.json.

The human review pass is the credibility of the whole eval — this script only
speeds it up and mechanizes the final assembly. Two independent steps:

  --triage   Ask an LLM critic to judge each candidate on the three failure
             modes that matter (answerable from THIS passage only? specific
             enough that few passages answer it? wording leaked?). Writes a
             `triage` block per candidate. This is an AID to human review, not
             a replacement — you still read and decide.

  --promote  Assemble gold.json from candidates you marked review_status="keep"
             (plus resolved hand-written questions), stripping scratch fields.
             Refuses to run if nothing is marked keep, so you can't skip review.

Typical flow:
    python evals/review_gold.py --triage          # annotate (optional, costs API)
    # ... hand-review gold_candidates.json: set review_status keep/reject ...
    python evals/review_gold.py --promote         # -> evals/gold.json
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import _bootstrap  # noqa: F401

from config import config
from langchain_groq import ChatGroq

EVALS = Path(__file__).resolve().parent
CANDIDATES = EVALS / "gold_candidates.json"
HANDWRITTEN = EVALS / "handwritten.json"
GOLD = EVALS / "gold.json"

TRIAGE_MODEL = "llama-3.3-70b-versatile"

TRIAGE_SYSTEM = (
    "You audit evaluation questions for a passage-retrieval benchmark. "
    "You are given a passage and a question meant to be answered by it.\n"
    "Judge three things:\n"
    "  answerable  — can the question be answered from THIS passage? (true/false)\n"
    "  specific    — is it specific enough that only a few passages could answer "
    "it, rather than a broad theme dozens of passages share? (true/false)\n"
    "  leaks       — does the question copy distinctive wording from the passage? "
    "(true/false)\n"
    "A GOOD question is answerable=true, specific=true, leaks=false.\n"
    'Respond ONLY with compact JSON: '
    '{"answerable":bool,"specific":bool,"leaks":bool,"verdict":"keep|borderline|reject","reason":"<=12 words"}'
)


def _triage_llm(model: str) -> ChatGroq:
    return ChatGroq(model=model, api_key=config.GROQ_API_KEY, temperature=0.0, max_tokens=160)


def _parse_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {"verdict": "borderline", "reason": "unparseable triage output"}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"verdict": "borderline", "reason": "unparseable triage output"}


def triage(model: str) -> None:
    items = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    llm = _triage_llm(model)
    counts = {"keep": 0, "borderline": 0, "reject": 0}
    for i, it in enumerate(items):
        passage = it.get("passage_preview", "")
        resp = llm.invoke([
            {"role": "system", "content": TRIAGE_SYSTEM},
            {"role": "user", "content": f"Passage:\n{passage}\n\nQuestion: {it['question']}"},
        ])
        verdict = _parse_json(resp.content)
        it["triage"] = verdict
        v = verdict.get("verdict", "borderline")
        counts[v] = counts.get(v, 0) + 1
        print(f"  [{i + 1:>3}/{len(items)}] {v:<10} {it['question'][:64]}")
    CANDIDATES.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nTriage written back to {CANDIDATES.name}: {counts}")
    print("This is guidance only — hand-review before promoting.")


_KEEP = {"keep", "kept", "yes", "y", "true"}
_GOLD_FIELDS = ("question", "gold_chunk_id", "accepted_alternates",
                "volume", "book", "chapter", "source", "split")


def _slim(it: dict) -> dict:
    out = {k: it[k] for k in _GOLD_FIELDS if k in it and it[k] is not None}
    out.setdefault("split", "dev")
    return out


def promote() -> None:
    cands = json.loads(CANDIDATES.read_text(encoding="utf-8")) if CANDIDATES.exists() else []
    kept = [c for c in cands if str(c.get("review_status", "")).lower() in _KEEP]

    hand = []
    if HANDWRITTEN.exists():
        for h in json.loads(HANDWRITTEN.read_text(encoding="utf-8")):
            if h.get("gold_chunk_id") is not None:
                hand.append(h)

    if not kept and not hand:
        raise SystemExit(
            "Nothing to promote.\n"
            "  • In gold_candidates.json, set \"review_status\": \"keep\" on the questions you keep.\n"
            "  • Run resolve_gold.py to give hand-written questions a gold_chunk_id.\n"
            "Refusing to build gold.json without a review pass."
        )

    gold = [_slim(c) for c in kept] + [_slim(h) for h in hand]
    GOLD.write_text(json.dumps(gold, indent=2, ensure_ascii=False), encoding="utf-8")

    n_test = sum(1 for g in gold if g.get("split") == "test")
    print(f"Wrote {len(gold)} gold questions to {GOLD.name} "
          f"({len(kept)} synthetic kept + {len(hand)} hand).")
    print(f"  split: {len(gold) - n_test} dev / {n_test} test")
    if n_test < 20:
        print("  ⚠ fewer than 20 held-out 'test' questions — set split=\"test\" on "
              "~30 items you won't tune on, per the eval plan.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Triage / promote gold candidates")
    ap.add_argument("--triage", action="store_true", help="LLM critic pass over candidates")
    ap.add_argument("--promote", action="store_true", help="build gold.json from kept items")
    ap.add_argument("--model", default=TRIAGE_MODEL)
    args = ap.parse_args()

    if not (args.triage or args.promote):
        ap.error("choose --triage and/or --promote")
    if args.triage:
        triage(args.model)
    if args.promote:
        promote()


if __name__ == "__main__":
    main()
