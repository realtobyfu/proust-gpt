#!/usr/bin/env python3
"""
Refine deviant passages using Cohere sentence-level embeddings.

Identifies passages that are too long or have extreme EN/FR length ratios,
groups consecutive deviants, and re-aligns them using Cohere embeddings
+ DP monotonic matching at sentence granularity.

Usage:
    cd backend
    python scripts/refine_alignment.py              # Dry-run (show deviants only)
    python scripts/refine_alignment.py --apply       # Apply refinement
    python scripts/refine_alignment.py --apply --max-groups 5  # Limit groups (testing)
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from langchain_cohere import CohereEmbeddings
from config import config

# ── Config ────────────────────────────────────────────────────────────────────

CORPUS_PATH = Path(__file__).parent.parent / "parsed_clean_bilingual.json"

MAX_CHUNK_CHARS = 750
MIN_CHUNK_CHARS = 250
DEVIANT_SIZE_THRESHOLD = 2000     # passages longer than this
DEVIANT_RATIO_THRESHOLD = 3.0     # EN/FR ratio above this
GROUP_GAP_TOLERANCE = 2           # merge groups separated by <= N good passages
GROUP_CONTEXT_RADIUS = 3          # include N good passages on each side of a group
BATCH_SIZE = 96                   # Cohere batch limit
RATE_LIMIT_DELAY = 0.5            # seconds between batches (production tier)

# ── Sentence splitting ────────────────────────────────────────────────────────

# Level 1: standard sentence boundaries (EN + FR)
_SENT_L1 = re.compile(
    r'(?<=[.!?\u2026\u00BB])\s+(?=[A-ZÀ-Ö\u00AB"\u201C\u2014])'
)

# Level 2: also split on ; and : when followed by uppercase/quote
_SENT_L2 = re.compile(
    r'(?<=[.!?\u2026\u00BB;:])\s+(?=[A-ZÀ-Ö\u00AB"\u201C\u2014])'
)

# Level 3: split on any punctuation + whitespace (last resort for Proust's
# 3000+ char sentences)
_SENT_L3 = re.compile(
    r'(?<=[.!?\u2026;,])\s+'
)


def split_sentences(text: str, min_sent_len: int = 30) -> list[str]:
    """Split text into sentences with progressively aggressive splitting.

    Tries standard sentence boundaries first, then falls back to
    semicolons/colons, then commas, to handle Proust's extremely long
    run-on sentences.
    """
    text = text.strip()
    if not text:
        return []

    # Try each level until we get multiple parts
    for regex in (_SENT_L1, _SENT_L2, _SENT_L3):
        parts = regex.split(text)
        if len(parts) > 1:
            break
    else:
        return [text]

    # Merge very short fragments
    result: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if result and len(result[-1]) < min_sent_len:
            result[-1] = result[-1] + " " + p
        else:
            result.append(p)
    # Merge trailing short fragment
    if len(result) > 1 and len(result[-1]) < min_sent_len:
        result[-2] = result[-2] + " " + result[-1]
        result.pop()

    return result


# ── Deviant detection ─────────────────────────────────────────────────────────

def is_deviant(p: dict) -> bool:
    """Check if a passage is deviant (too long or extreme ratio)."""
    en_l = len(p.get("text", ""))
    fr_l = len(p.get("text_fr", ""))
    if max(en_l, fr_l) > DEVIANT_SIZE_THRESHOLD:
        return True
    if en_l > 0 and fr_l > 0:
        ratio = max(en_l, fr_l) / min(en_l, fr_l)
        if ratio > DEVIANT_RATIO_THRESHOLD:
            return True
    return False


def find_deviant_groups(passages: list[dict]) -> list[list[int]]:
    """Find groups of consecutive deviant passage indices.

    Merges groups separated by <= GROUP_GAP_TOLERANCE good passages,
    then expands each group by GROUP_CONTEXT_RADIUS on each side
    (staying within the same chapter) so Cohere can redistribute
    text from neighbors.
    """
    deviant_indices = [i for i, p in enumerate(passages) if is_deviant(p)]
    if not deviant_indices:
        return []

    # Group consecutive indices (with gap tolerance)
    raw_groups: list[list[int]] = []
    current_group = [deviant_indices[0]]

    for idx in deviant_indices[1:]:
        if idx - current_group[-1] <= GROUP_GAP_TOLERANCE + 1:
            # Fill in the gap (include non-deviant passages between deviants)
            for fill in range(current_group[-1] + 1, idx):
                current_group.append(fill)
            current_group.append(idx)
        else:
            raw_groups.append(current_group)
            current_group = [idx]

    raw_groups.append(current_group)

    # Expand each group with context, staying in same chapter
    expanded_groups: list[list[int]] = []
    for group in raw_groups:
        chapter = passages[group[0]].get("chapter")
        volume = passages[group[0]].get("volume")
        start = group[0]
        end = group[-1]

        # Expand left
        for _ in range(GROUP_CONTEXT_RADIUS):
            if start > 0 and passages[start - 1].get("chapter") == chapter \
                    and passages[start - 1].get("volume") == volume:
                start -= 1
        # Expand right
        for _ in range(GROUP_CONTEXT_RADIUS):
            if end < len(passages) - 1 and passages[end + 1].get("chapter") == chapter \
                    and passages[end + 1].get("volume") == volume:
                end += 1

        expanded_groups.append(list(range(start, end + 1)))

    # Merge overlapping expanded groups
    merged: list[list[int]] = []
    for group in expanded_groups:
        if merged and group[0] <= merged[-1][-1] + 1:
            # Merge with previous
            combined = sorted(set(merged[-1] + group))
            merged[-1] = combined
        else:
            merged.append(group)

    return merged


# ── Cohere embedding ──────────────────────────────────────────────────────────

def embed_sentences(
    sentences: list[str],
    embeddings: CohereEmbeddings,
) -> np.ndarray:
    """Embed sentences in batches with rate limiting."""
    all_vecs = []
    for i in range(0, len(sentences), BATCH_SIZE):
        batch = sentences[i:i + BATCH_SIZE]
        vecs = embeddings.embed_documents(batch)
        all_vecs.extend(vecs)
        if i + BATCH_SIZE < len(sentences):
            time.sleep(RATE_LIMIT_DELAY)
    return np.array(all_vecs)


# ── DP monotonic alignment ───────────────────────────────────────────────────

def dp_align_sentences(
    en_vecs: np.ndarray,
    fr_vecs: np.ndarray,
) -> list[tuple[list[int], list[int]]]:
    """Monotonic DP alignment of EN sentences to FR sentences.

    Returns list of (en_indices, fr_indices) aligned groups.
    Each FR sentence is assigned to exactly one group; EN sentences
    may be grouped (many-to-one) to match FR.
    """
    n_en = len(en_vecs)
    n_fr = len(fr_vecs)

    if n_en == 0 or n_fr == 0:
        return [(list(range(n_en)), list(range(n_fr)))]

    # Cosine similarity matrix
    # Normalize vectors
    en_norm = en_vecs / (np.linalg.norm(en_vecs, axis=1, keepdims=True) + 1e-10)
    fr_norm = fr_vecs / (np.linalg.norm(fr_vecs, axis=1, keepdims=True) + 1e-10)
    sim = en_norm @ fr_norm.T  # (n_en, n_fr)

    # For each EN sentence, find best matching FR sentence
    en_to_fr = np.argmax(sim, axis=1)

    # Enforce monotonicity: if assignment goes backwards, push forward
    for i in range(1, n_en):
        if en_to_fr[i] < en_to_fr[i - 1]:
            en_to_fr[i] = en_to_fr[i - 1]

    # Group EN sentences by their assigned FR sentence
    groups: list[tuple[list[int], list[int]]] = []
    current_en: list[int] = []
    current_fr_idx = -1

    for en_idx in range(n_en):
        fr_idx = en_to_fr[en_idx]
        if fr_idx != current_fr_idx:
            if current_en:
                # Flush: assign FR sentences from previous boundary to current
                fr_start = en_to_fr[current_en[0]] if current_en else 0
                fr_end = fr_idx
                groups.append((current_en, list(range(fr_start, fr_end))))
            current_en = [en_idx]
            current_fr_idx = fr_idx
        else:
            current_en.append(en_idx)

    # Last group
    if current_en:
        fr_start = en_to_fr[current_en[0]]
        groups.append((current_en, list(range(fr_start, n_fr))))

    # Fill any unassigned FR sentences
    assigned_fr = set()
    for _, fr_indices in groups:
        assigned_fr.update(fr_indices)
    unassigned = [i for i in range(n_fr) if i not in assigned_fr]
    if unassigned and groups:
        # Add unassigned FR to the nearest group
        for fr_idx in unassigned:
            best_group = 0
            best_dist = float("inf")
            for g_idx, (_, fr_indices) in enumerate(groups):
                if fr_indices:
                    d = min(abs(fr_idx - f) for f in fr_indices)
                else:
                    d = fr_idx
                if d < best_dist:
                    best_dist = d
                    best_group = g_idx
            groups[best_group][1].append(fr_idx)
            groups[best_group][1].sort()

    return groups


# ── Re-chunking ──────────────────────────────────────────────────────────────

def _split_pair_proportionally(
    en_text: str, fr_text: str, n_sub: int,
) -> list[tuple[str, str]]:
    """Split EN and FR texts proportionally into n_sub sub-pairs."""
    en_sents = split_sentences(en_text)
    fr_sents = split_sentences(fr_text)

    en_per = max(1, len(en_sents) // n_sub)
    fr_per = max(1, len(fr_sents) // n_sub)

    result = []
    for k in range(n_sub):
        en_start = k * en_per
        en_end = len(en_sents) if k == n_sub - 1 else (k + 1) * en_per
        fr_start = k * fr_per
        fr_end = len(fr_sents) if k == n_sub - 1 else (k + 1) * fr_per
        en_sub = " ".join(en_sents[en_start:en_end]).strip()
        fr_sub = " ".join(fr_sents[fr_start:fr_end]).strip()
        if en_sub or fr_sub:
            result.append((en_sub, fr_sub))

    return result if result else [(en_text, fr_text)]


def rechunk_aligned(
    en_sents: list[str],
    fr_sents: list[str],
    groups: list[tuple[list[int], list[int]]],
) -> list[tuple[str, str]]:
    """Convert aligned sentence groups into properly-sized chunks."""
    # Build aligned pairs from groups
    pairs: list[tuple[str, str]] = []
    for en_indices, fr_indices in groups:
        en_text = " ".join(en_sents[i] for i in en_indices if i < len(en_sents))
        fr_text = " ".join(fr_sents[i] for i in fr_indices if i < len(fr_sents))
        if en_text.strip() or fr_text.strip():
            pairs.append((en_text.strip(), fr_text.strip()))

    if not pairs:
        return []

    # Subdivide pairs that are still too long
    subdivided: list[tuple[str, str]] = []
    for en_text, fr_text in pairs:
        longer = max(len(en_text), len(fr_text))
        if longer > MAX_CHUNK_CHARS:
            n_sub = (longer + MAX_CHUNK_CHARS - 1) // MAX_CHUNK_CHARS
            subdivided.extend(_split_pair_proportionally(en_text, fr_text, n_sub))
        else:
            subdivided.append((en_text, fr_text))

    # Merge small pairs into chunks of MIN-MAX_CHUNK_CHARS
    chunks: list[tuple[str, str]] = []
    cur_en: list[str] = []
    cur_fr: list[str] = []
    cur_len = 0

    for en_text, fr_text in subdivided:
        size = max(len(en_text), len(fr_text))
        would_exceed = cur_len + size > MAX_CHUNK_CHARS

        if cur_en and would_exceed and cur_len >= MIN_CHUNK_CHARS:
            chunks.append((" ".join(cur_en), " ".join(cur_fr)))
            cur_en = []
            cur_fr = []
            cur_len = 0

        cur_en.append(en_text)
        cur_fr.append(fr_text)
        cur_len += size + 1

    if cur_en:
        chunks.append((" ".join(cur_en), " ".join(cur_fr)))

    return chunks


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Refine deviant passages with Cohere")
    parser.add_argument("--apply", action="store_true", help="Apply refinement (default: dry run)")
    parser.add_argument("--max-groups", type=int, default=None, help="Limit groups to process")
    args = parser.parse_args()

    print("Loading corpus...")
    with open(CORPUS_PATH, encoding="utf-8") as f:
        passages = json.load(f)
    print(f"  {len(passages)} passages")

    # Find deviant groups
    groups = find_deviant_groups(passages)
    total_deviants = sum(len(g) for g in groups)
    print(f"\nFound {len(groups)} deviant groups ({total_deviants} passages)")

    # Show summary
    for i, group in enumerate(groups[:20]):
        indices = [passages[j]["index"] for j in group]
        vols = set(passages[j]["volume"] for j in group)
        en_total = sum(len(passages[j]["text"]) for j in group)
        fr_total = sum(len(passages[j].get("text_fr", "")) for j in group)
        print(f"  Group {i+1}: {len(group)} passages, "
              f"vol={vols}, idx={indices[0]}-{indices[-1]}, "
              f"EN={en_total:,} FR={fr_total:,}")
    if len(groups) > 20:
        print(f"  ... and {len(groups) - 20} more groups")

    if not args.apply:
        print("\nDry run. Use --apply to refine.")
        return

    # Estimate API calls
    total_chars = sum(
        len(passages[j]["text"]) + len(passages[j].get("text_fr", ""))
        for g in groups for j in g
    )
    est_sents = total_chars // 80
    est_batches = (est_sents + BATCH_SIZE - 1) // BATCH_SIZE
    est_time = est_batches * RATE_LIMIT_DELAY / 60
    print(f"\nEstimated: ~{est_sents} sentences, ~{est_batches} API batches, "
          f"~{est_time:.0f} min")

    # Initialize Cohere
    print("\nInitializing Cohere embeddings...")
    embeddings = CohereEmbeddings(
        model=config.COHERE_EMBED_MODEL,
        cohere_api_key=config.COHERE_API_KEY,
    )

    # Process groups
    max_groups = args.max_groups or len(groups)
    replacements: list[tuple[list[int], list[dict]]] = []

    for g_idx, group in enumerate(groups[:max_groups]):
        vol = passages[group[0]]["volume"]
        chapter = passages[group[0]]["chapter"]
        book = passages[group[0]]["book"]

        # Combine EN and FR text from the group
        en_combined = " ".join(passages[j]["text"] for j in group)
        fr_combined = " ".join(passages[j].get("text_fr", "") for j in group)

        en_sents = split_sentences(en_combined)
        fr_sents = split_sentences(fr_combined)

        print(f"\n  Group {g_idx+1}/{max_groups}: vol={vol} ch={chapter[:30]}, "
              f"{len(group)} passages → {len(en_sents)} EN sents + {len(fr_sents)} FR sents")

        if not en_sents or not fr_sents:
            print("    Skipping (empty text on one side)")
            continue

        # Embed
        all_sents = en_sents + fr_sents
        print(f"    Embedding {len(all_sents)} sentences...")
        vecs = embed_sentences(all_sents, embeddings)

        en_vecs = vecs[:len(en_sents)]
        fr_vecs = vecs[len(en_sents):]

        # DP align
        aligned_groups = dp_align_sentences(en_vecs, fr_vecs)

        # Re-chunk
        chunks = rechunk_aligned(en_sents, fr_sents, aligned_groups)

        # Build replacement records
        new_records = []
        for en_chunk, fr_chunk in chunks:
            new_records.append({
                "text": en_chunk.strip(),
                "text_fr": fr_chunk.strip(),
                "volume": vol,
                "chapter": chapter,
                "book": book,
            })

        replacements.append((group, new_records))

        # Stats
        new_sizes = [max(len(r["text"]), len(r.get("text_fr", ""))) for r in new_records]
        avg_size = sum(new_sizes) / len(new_sizes) if new_sizes else 0
        max_size = max(new_sizes) if new_sizes else 0
        print(f"    → {len(new_records)} chunks (avg={avg_size:.0f}, max={max_size})")

    # Apply replacements (in reverse order to preserve indices)
    print(f"\n{'='*60}")
    print(f"Applying {len(replacements)} group replacements...")

    for group_indices, new_records in reversed(replacements):
        start = group_indices[0]
        end = group_indices[-1] + 1
        passages[start:end] = new_records

    # Re-index
    for i, p in enumerate(passages, start=1):
        p["index"] = i

    # Stats
    print(f"\nFinal corpus: {len(passages)} passages")
    deviants_remaining = sum(1 for p in passages if is_deviant(p))
    print(f"Deviants remaining: {deviants_remaining}")

    en_lens = [len(p["text"]) for p in passages]
    fr_lens = [len(p.get("text_fr", "")) for p in passages if p.get("text_fr")]
    print(f"EN length: avg={sum(en_lens)/len(en_lens):.0f}, "
          f"max={max(en_lens)}, min={min(en_lens)}")
    if fr_lens:
        print(f"FR length: avg={sum(fr_lens)/len(fr_lens):.0f}, "
              f"max={max(fr_lens)}, min={min(fr_lens)}")

    # Save
    with open(CORPUS_PATH, "w", encoding="utf-8") as f:
        json.dump(passages, f, ensure_ascii=False, indent=2)
    print(f"\nSaved {len(passages)} passages to {CORPUS_PATH}")


if __name__ == "__main__":
    main()
