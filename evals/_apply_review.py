"""One-shot reviewer pass: mark keep/reject, assign split, fix handwritten gold.

Not part of the harness — a record of the review decisions applied on
2026-07-13. Rerunnable/idempotent against the committed candidate file.
"""
import json
import random
from pathlib import Path

EV = Path(__file__).resolve().parent

# ── Synthetic rejection rules (keyed off reliable JSON fields, not typed ids) ──
# many-answer / aphoristic questions: dozens of passages could answer, so scoring
# against one chunk is unfair. Matched by question substring (robust to ids).
AMBIGUOUS_SUBSTR = [
    "memories of past conflicts or unpleasant interactions",
    "lacking in the actions of people who frequently express virtuous",
    "benefit does the approach of demystifying things",
    "more helpful in winning someone's heart than",
    "want to eat when feeling cold",
    "type of things did the narrator feel made the world more beautiful",
    "activity could the narrator have done for hours, similar",
    "ability had the person's body been trained to perform in various social",
]


def should_reject(c: dict) -> bool:
    t = c.get("triage", {})
    # LLM critic flagged bad gold mapping or non-specific
    if t.get("verdict") == "reject" or t.get("answerable") is False or t.get("specific") is False:
        return True
    # strong lexical leak: 5+ word verbatim run shared -> trivially found
    if c["leakage"]["max_shared_ngram"] >= 5:
        return True
    # many-answer / aphoristic
    if any(s in c["question"] for s in AMBIGUOUS_SUBSTR):
        return True
    return False

# ── Handwritten gold assignments (verified against passage text) ───────────────
# key substring -> (gold_chunk_id, [accepted_alternates])
HAND = {
    "madeleine scene happen": (196, [199, 197]),
    "Montjouvain": (460, [654]),
    "goodnight kiss": (40, []),
    "moving steeples": (740, [738]),
    "flowers along a hedge": (566, []),
    "never really his type": (1548, []),
    "musical phrase becomes a private emblem": (964, [1398]),
    "magic-lantern figures": (25, [26, 27]),
    "uneven paving underfoot": (11805, [11808, 11836]),
    "age has disfigured the guests": (12030, [12092, 12053]),
    "waking in the dark": (20, [12, 762, 22]),
}
HAND_DROP = "grandmother behave during their walks"  # mis-framed vs text -> cut


def apply_candidates():
    path = EV / "gold_candidates.json"
    cands = json.loads(path.read_text(encoding="utf-8"))
    for c in cands:
        c["review_status"] = "reject" if should_reject(c) else "keep"

    # Stratified test holdout among the KEEPERS: ~20 across volumes, seeded.
    keepers = [c for c in cands if c["review_status"] == "keep"]
    rng = random.Random(29)
    by_vol = {}
    for c in keepers:
        by_vol.setdefault(c["volume"], []).append(c)
    test_ids = set()
    target, per_vol = 20, {}
    vols = sorted(by_vol)
    for v in vols:
        rng.shuffle(by_vol[v])
        per_vol[v] = max(2, round(target * len(by_vol[v]) / len(keepers)))
    for v in vols:
        for c in by_vol[v][: per_vol[v]]:
            test_ids.add(c["gold_chunk_id"])
    for c in cands:
        c["split"] = "test" if c["gold_chunk_id"] in test_ids else "dev"

    path.write_text(json.dumps(cands, indent=2, ensure_ascii=False), encoding="utf-8")
    kept = sum(1 for c in cands if c["review_status"] == "keep")
    return kept, len(cands) - kept, len(test_ids)


def apply_handwritten():
    path = EV / "handwritten.json"
    items = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for it in items:
        q = it["question"]
        if HAND_DROP in q:
            continue
        for key, (gold, alts) in HAND.items():
            if key in q:
                it["gold_chunk_id"] = gold
                if alts:
                    it["accepted_alternates"] = alts
                it["review_status"] = "keep"
                break
        out.append(it)
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    unresolved = [i["question"][:50] for i in out if i.get("gold_chunk_id") is None]
    return len(out), unresolved


if __name__ == "__main__":
    kept, rejected, syn_test = apply_candidates()
    n_hand, unresolved = apply_handwritten()
    print(f"synthetic: {kept} keep / {rejected} reject  ({syn_test} synthetic in test split)")
    print(f"handwritten: {n_hand} kept (all test), unresolved={unresolved}")
