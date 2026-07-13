#!/usr/bin/env python3
"""
Build gold-set *candidates* for the retrieval eval.

Pipeline (Step 1 of the eval plan):
  1. Stratified-sample chunks across the seven volumes (proportional, with a
     floor so small volumes are represented), filtered to chunks long enough
     to actually answer a question.
  2. Keep only chunks that exist in the Pinecone EN namespace (some corpus
     rows were never ingested).
  3. For each, ask the LLM to write ONE question the chunk answers — WITHOUT
     reusing distinctive wording. If the question copies the chunk's words,
     embedding search finds it trivially and the score is fake-high.
  4. Flag lexical leakage (shared 4-grams / rare content words) so the human
     reviewer can catch trivially-matchable questions fast.

Output: evals/gold_candidates.json  (review_status="pending")

This script does NOT produce the gold set. The human review pass — deleting
unanswerable / ambiguous / many-answer questions — is the actual work and the
actual credibility. After review, save the kept items as evals/gold.json.

Usage:
    python evals/build_gold.py                 # ~120 candidates, seed=13
    python evals/build_gold.py -n 20           # quick test batch
    python evals/build_gold.py --seed 7 -n 120
    python evals/build_gold.py --out evals/gold_candidates.json
"""
from __future__ import annotations

import argparse
import json
import random
import re
from collections import defaultdict
from pathlib import Path

import _bootstrap  # noqa: F401

from config import config
from langchain_groq import ChatGroq
from retrieval import get_pinecone_index

EVALS = Path(__file__).resolve().parent
CORPUS = _bootstrap.BACKEND / "parsed_clean_bilingual.json"
DEFAULT_OUT = EVALS / "gold_candidates.json"

MIN_CHARS = 350          # chunk must be long enough to answer a real question
MAX_PREVIEW = 600        # stored preview length for the reviewer
DEFAULT_N = 120
DEFAULT_SEED = 13

# Question generation is decoupled from the app's LLM config on purpose: it
# only needs a capable instruct model, and the app's configured model may be
# unavailable. Override with --model.
QGEN_MODEL = "llama-3.3-70b-versatile"

_STOPWORDS = set(
    "the a an and or but of to in on at for with from by as is was were be been being "
    "that this these those it its he she they them his her their i you we me my our your "
    "not no so if then than which who whom whose what when where why how all any some more "
    "most other into out up down over under again further once here there about against "
    "between through during before after above below only own same too very can will just "
    "had has have do does did having would could should may might must one two had".split()
)

QGEN_SYSTEM = (
    "You write evaluation questions for a Proust retrieval system. "
    "Given ONE passage from 'In Search of Lost Time', write a single question "
    "that this specific passage answers.\n"
    "Rules:\n"
    "1. The question must be answerable from THIS passage alone.\n"
    "2. Do NOT quote or reuse distinctive phrases from the passage. Never copy "
    "any run of 3+ consecutive words. Describe events, objects and sensations "
    "in your own words.\n"
    "3. Prefer paraphrase over the passage's rare vocabulary. A proper name is "
    "allowed ONLY if the question would otherwise be ambiguous.\n"
    "4. Ask about something concrete and specific to this passage, not a broad "
    "theme that dozens of passages could answer.\n"
    "5. One sentence, ending in '?'. Output ONLY the question, nothing else."
)


# ── Corpus sampling ───────────────────────────────────────────────────────────

def load_corpus() -> list[dict]:
    return json.loads(CORPUS.read_text(encoding="utf-8"))


def eligible(p: dict) -> bool:
    text = p.get("text", "") or ""
    if len(text) < MIN_CHARS:
        return False
    # Skip chunks that are mostly non-prose (tables of dashes, headings, etc.)
    letters = sum(c.isalpha() for c in text)
    return letters / max(len(text), 1) > 0.6 and p.get("index") is not None


def stratified_sample(passages: list[dict], n: int, rng: random.Random) -> list[dict]:
    by_vol: dict[int, list[dict]] = defaultdict(list)
    for p in passages:
        if eligible(p):
            by_vol[p.get("volume", 1)].append(p)

    vols = sorted(by_vol)
    total = sum(len(by_vol[v]) for v in vols)
    # Proportional allocation with a floor of ~8 per volume.
    alloc = {}
    for v in vols:
        share = round(n * len(by_vol[v]) / total)
        alloc[v] = max(8, share)

    picked: list[dict] = []
    for v in vols:
        pool = by_vol[v]
        rng.shuffle(pool)
        picked.extend(pool[: alloc[v]])
    rng.shuffle(picked)
    return picked[:n] if len(picked) > n else picked


def filter_in_index(passages: list[dict], namespace: str = "en") -> list[dict]:
    """Keep only passages whose `passage-{index}` id exists in the index."""
    index = get_pinecone_index()
    kept: list[dict] = []
    for i in range(0, len(passages), 100):
        batch = passages[i : i + 100]
        ids = [f"passage-{p['index']}" for p in batch]
        found = index.fetch(ids=ids, namespace=namespace).vectors
        for p in batch:
            if f"passage-{p['index']}" in found:
                kept.append(p)
    return kept


# ── Leakage detection ─────────────────────────────────────────────────────────

def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z]+", text.lower())


def _content_tokens(text: str) -> set[str]:
    return {t for t in _tokens(text) if t not in _STOPWORDS and len(t) > 3}


def max_shared_ngram(question: str, passage: str, max_n: int = 8) -> int:
    """Longest run of consecutive words shared between question and passage."""
    q = _tokens(question)
    p_ngrams_cache: dict[int, set] = {}
    best = 0
    for n in range(2, min(max_n, len(q)) + 1):
        if n not in p_ngrams_cache:
            pw = _tokens(passage)
            p_ngrams_cache[n] = {tuple(pw[i : i + n]) for i in range(len(pw) - n + 1)}
        q_ngrams = {tuple(q[i : i + n]) for i in range(len(q) - n + 1)}
        if q_ngrams & p_ngrams_cache[n]:
            best = n
    return best


def leakage(question: str, passage: str) -> dict:
    shared_tokens = sorted(_content_tokens(question) & _content_tokens(passage))
    return {
        "max_shared_ngram": max_shared_ngram(question, passage),
        "shared_content_tokens": shared_tokens,
        "num_shared_tokens": len(shared_tokens),
    }


# ── Question generation ───────────────────────────────────────────────────────

def make_llm(model: str = QGEN_MODEL) -> ChatGroq:
    return ChatGroq(
        model=model,
        api_key=config.GROQ_API_KEY,
        temperature=0.7,
        max_tokens=120,
    )


def clean_question(raw: str) -> str:
    q = raw.strip().strip('"').strip()
    # Drop any leading label like "Question:" the model may add.
    q = re.sub(r"^(question|q)\s*[:\-]\s*", "", q, flags=re.I).strip()
    # Keep only the first line / sentence-ish.
    q = q.splitlines()[0].strip()
    return q


def generate_question(llm: ChatGroq, passage_text: str, retries: int = 1) -> str:
    excerpt = passage_text[:1600]
    for attempt in range(retries + 1):
        resp = llm.invoke([
            {"role": "system", "content": QGEN_SYSTEM},
            {"role": "user", "content": f"Passage:\n{excerpt}\n\nQuestion:"},
        ])
        q = clean_question(resp.content)
        # Regenerate once if it copied a 4+ word run verbatim.
        if max_shared_ngram(q, passage_text) < 4 or attempt == retries:
            return q
    return q


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Build gold-set candidates")
    ap.add_argument("-n", type=int, default=DEFAULT_N, help="target candidate count")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--lang", default="en", help="Pinecone namespace to verify against")
    ap.add_argument("--model", default=QGEN_MODEL, help="Groq model for question generation")
    args = ap.parse_args()

    args.out = args.out.resolve()
    rng = random.Random(args.seed)
    print(f"Loading corpus from {CORPUS.name} …")
    passages = load_corpus()

    # Oversample before the index-existence filter so we still land near n.
    sample = stratified_sample(passages, int(args.n * 1.25), rng)
    print(f"Sampled {len(sample)} eligible chunks; verifying against Pinecone …")
    sample = filter_in_index(sample, namespace=args.lang)
    sample = sample[: args.n]
    print(f"{len(sample)} chunks confirmed in index. Generating questions …")

    llm = make_llm(args.model)
    print(f"Question-generation model: {args.model}")
    candidates: list[dict] = []
    for i, p in enumerate(sample):
        text = p["text"]
        q = generate_question(llm, text)
        leak = leakage(q, text)
        candidates.append({
            "gold_chunk_id": int(p["index"]),
            "volume": p.get("volume"),
            "book": p.get("book"),
            "chapter": p.get("chapter"),
            "source": "synthetic",
            "split": "dev",
            "question": q,
            "passage_preview": text[:MAX_PREVIEW] + ("…" if len(text) > MAX_PREVIEW else ""),
            "passage_len": len(text),
            "leakage": leak,
            "review_status": "pending",
        })
        flag = "  ⚠ leak" if leak["max_shared_ngram"] >= 4 else ""
        print(f"  [{i + 1:>3}/{len(sample)}] vol{p.get('volume')} #{p['index']}{flag}  {q[:70]}")

    args.out.write_text(json.dumps(candidates, indent=2, ensure_ascii=False), encoding="utf-8")

    leaky = sum(1 for c in candidates if c["leakage"]["max_shared_ngram"] >= 4)
    print(f"\nWrote {len(candidates)} candidates to {args.out}")
    print(f"  {leaky} flagged for lexical leakage (4+ word overlap) — review these first.")
    print("\nNext: hand-review the file. Delete unanswerable / ambiguous / many-answer")
    print("questions, set 'split' to \"test\" for ~30 held-out items, then save kept")
    print("items as evals/gold.json.")


if __name__ == "__main__":
    main()
