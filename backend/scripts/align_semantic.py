#!/usr/bin/env python3
"""
Semantic paragraph alignment using Cohere embeddings.

Replaces the proportional position-based alignment in align_paragraphs.py
with cosine-similarity-based matching. Uses dynamic programming to enforce
monotonic order (paragraphs can't be reordered).

Algorithm:
1. Split each EN and FR chapter into paragraphs (preserving paragraph boundaries)
2. Embed all paragraphs with Cohere embed-v4.0 (multilingual)
3. For each chapter, compute cosine similarity matrix between EN and FR paragraphs
4. Use DP to find optimal monotonic alignment (maximizes total similarity)

This produces much better EN-FR alignment than proportional position mapping,
especially when paragraph counts differ between languages.

Usage:
    cd backend
    python scripts/align_semantic.py
    python scripts/align_semantic.py --delay 12  # slower, for trial API keys
"""

import argparse
import json
import os
import re
import sys
import time
import numpy as np
from pathlib import Path
from collections import Counter

from dotenv import load_dotenv
load_dotenv()

import cohere

# ── Paths ────────────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).parent.parent / "data"
EN_DIR = DATA_DIR / "english_raw"
FR_DIR = DATA_DIR / "french_raw"
OUTPUT_PATH = DATA_DIR / "aligned_paragraphs.json"

# ── Chapter mapping (same as align_paragraphs.py) ───────────────────────────

EN_TO_FR_CHAPTER_MAP = {
    # Vol 1: EN has 3 chapters, FR has 3 parts
    (1, "Overture"): [0],
    (1, "Swann in Love"): [1],
    (1, "Place-Names: The Name"): [2],

    # Vol 2: EN has 3 chapters, FR has 3 parts
    (2, "Madame Swann at Home"): [0],
    (2, "Place-Names: The Place"): [1],
    (2, "Seascape, with Frieze of Girls"): [2],

    # Vol 3: EN has 3 parts matching FR's 3 parts (1:1)
    (3, "Part 1"): [0],
    (3, "Part 2"): [1],
    (3, "Part 3"): [2],

    # Vol 4: EN has 5 chapters, FR has 5 sections
    (4, "Introduction"): [0],
    (4, "Chapter 1"): [1],
    (4, "Chapter 2"): [2],
    (4, "Chapter 3"): [3],
    (4, "Chapter 4"): [4],

    # Vol 5: EN has 3 chapters, FR has 3 chapters
    (5, "Chapter 1 \u2014 Life with Albertine"): [0],
    (5, "Chapter 2 \u2014 The Verdurins Quarrel with M. De Charlus"): [1],
    (5, "Chapter 3 \u2014 Flight of Albertine"): [2],

    # Vol 6: EN has 4 chapters, FR has 4 chapters
    (6, "Chapter 1 \u2014 Grief and Oblivion"): [0],
    (6, "Chapter 2 \u2014 Mademoiselle De Forcheville"): [1],
    (6, "Chapter 3 \u2014 Venice"): [2],
    (6, "Chapter 4 \u2014 A Fresh Light Upon Robert De Saint-Loup"): [3],

    # Vol 7: EN has 3 chapters, FR has 3 chapters
    (7, "Chapter 1 \u2014 Tansonville"): [0],
    (7, "Chapter 2 \u2014 M. de Charlus During the War, His Opinions, His Pleasures"): [1],
    (7, "Chapter 3 \u2014 An Afternoon Party at the House of the Princesse de Guermantes"): [2],
}


# ── Text splitting ──────────────────────────────────────────────────────────

def split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs on double-newline boundaries.

    Returns non-empty paragraphs with internal whitespace normalized.
    """
    raw = re.split(r"\n\s*\n", text)
    paragraphs = []
    for p in raw:
        cleaned = p.strip()
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        if cleaned:
            paragraphs.append(cleaned)
    return paragraphs


# ── Cohere embedding ────────────────────────────────────────────────────────

def embed_texts(
    co: cohere.Client,
    texts: list[str],
    batch_size: int = 96,
    delay: float = 1.0,
    label: str = "",
) -> np.ndarray:
    """Embed texts in batches with rate limiting and retries.

    Args:
        co: Cohere client
        texts: List of texts to embed
        batch_size: Max texts per API call (Cohere limit is 96)
        delay: Seconds between API calls (use 12 for trial keys)
        label: Label for progress output

    Returns:
        numpy array of shape (len(texts), embedding_dim)
    """
    all_embeddings: list[list[float]] = []
    total_batches = (len(texts) + batch_size - 1) // batch_size

    for batch_num, i in enumerate(range(0, len(texts), batch_size), 1):
        batch = texts[i:i + batch_size]
        print(f"    {label} batch {batch_num}/{total_batches} "
              f"({len(all_embeddings)}/{len(texts)} done)", end="\r")

        for attempt in range(5):
            try:
                response = co.embed(
                    texts=batch,
                    model="embed-v4.0",
                    input_type="search_document",
                    embedding_types=["float"],
                )
                all_embeddings.extend(response.embeddings.float_)
                break
            except Exception as e:
                err = str(e).lower()
                if ("rate" in err or "429" in err) and attempt < 4:
                    wait = delay * (2 ** attempt)
                    print(f"\n    Rate limited, waiting {wait:.0f}s...")
                    time.sleep(wait)
                    continue
                raise

        if i + batch_size < len(texts):
            time.sleep(delay)

    print(f"    {label} embedded {len(all_embeddings)} texts" + " " * 20)
    return np.array(all_embeddings)


# ── Alignment algorithms ────────────────────────────────────────────────────

def cosine_similarity_matrix(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    """Compute cosine similarity matrix between two sets of embeddings.

    Args:
        A: shape (N, D) — EN paragraph embeddings
        B: shape (M, D) — FR paragraph embeddings

    Returns:
        shape (N, M) similarity matrix
    """
    A_norm = A / np.linalg.norm(A, axis=1, keepdims=True)
    B_norm = B / np.linalg.norm(B, axis=1, keepdims=True)
    return A_norm @ B_norm.T


def fr_primary_align(
    sim_matrix: np.ndarray,
    max_group: int = 8,
) -> list[tuple[list[int], int]]:
    """FR-primary alignment: partition the majority side into groups
    mapped 1:1 to the minority side. Guarantees no repeated text on either side.

    Output count = min(N_en, M_fr). The majority side's paragraphs are
    grouped into contiguous chunks; each group maps to exactly one paragraph
    on the minority side.

    Args:
        sim_matrix: shape (N_en, M_fr) cosine similarity matrix.
        max_group: Maximum paragraphs per group (bandwidth constraint).

    Returns:
        List of (source_indices, target_index) tuples.
        - When EN > FR: source_indices are EN indices, target_index is FR index.
        - When FR > EN: source_indices are FR indices, target_index is EN index.
        The caller must check which side is majority to interpret correctly.
    """
    N, M = sim_matrix.shape  # N = EN count, M = FR count

    if N == 0 or M == 0:
        return []

    # Determine majority side
    if N >= M:
        # EN is majority → partition N EN paragraphs into M groups
        # sim_matrix[i][j] already has EN as rows, FR as cols
        src_count, tgt_count = N, M
        # avg_sim for source[start:end] vs target[k] = mean(sim_matrix[start:end, k])
        get_sim = lambda start, end, k: float(np.mean(sim_matrix[start:end, k]))
    else:
        # FR is majority → partition M FR paragraphs into N groups
        src_count, tgt_count = M, N
        # Transpose: sim_matrix.T[j][i] = similarity of FR[j] to EN[i]
        sim_T = sim_matrix.T
        get_sim = lambda start, end, k: float(np.mean(sim_T[start:end, k]))

    # DP: partition src_count source paragraphs into tgt_count groups
    # dp[k][i] = best total score for first k target paragraphs
    #            using source[0:i]
    INF = -1e18
    dp = np.full((tgt_count + 1, src_count + 1), INF)
    back = np.zeros((tgt_count + 1, src_count + 1), dtype=int)
    dp[0][0] = 0.0

    for k in range(1, tgt_count + 1):
        # Remaining groups after this one: tgt_count - k
        # Each remaining group needs at least 1 paragraph
        remaining = tgt_count - k
        for i in range(k, src_count - remaining + 1):
            # Group k uses source[j:i] for some j
            # j must be >= k-1 (previous groups need at least k-1 paragraphs)
            best_score = INF
            best_j = k - 1
            lo = max(k - 1, i - max_group)
            for j in range(lo, i):
                if dp[k - 1][j] <= INF / 2:
                    continue
                score = dp[k - 1][j] + get_sim(j, i, k - 1)
                if score > best_score:
                    best_score = score
                    best_j = j
            dp[k][i] = best_score
            back[k][i] = best_j

    # Backtrack to find group boundaries
    boundaries = [0] * (tgt_count + 1)
    boundaries[tgt_count] = src_count
    for k in range(tgt_count, 0, -1):
        boundaries[k - 1] = back[k][boundaries[k]]

    # Build result
    result = []
    for k in range(tgt_count):
        start = boundaries[k]
        end = boundaries[k + 1]
        src_indices = list(range(start, end))
        tgt_idx = k
        result.append((src_indices, tgt_idx))

    return result


# ── Volume loading ──────────────────────────────────────────────────────────

def load_english_volumes() -> dict[int, dict]:
    english = {}
    for vol_file in sorted(EN_DIR.glob("volume_*.json")):
        with open(vol_file, encoding="utf-8") as f:
            data = json.load(f)
            english[data["volume"]] = data
    return english


def load_french_volumes() -> dict[int, dict]:
    french = {}
    for vol_file in sorted(FR_DIR.glob("volume_*.json")):
        with open(vol_file, encoding="utf-8") as f:
            data = json.load(f)
            french[data["volume"]] = data
    return french


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Semantic bilingual alignment")
    parser.add_argument("--delay", type=float, default=1.0,
                        help="Seconds between API calls (use 12 for trial keys)")
    parser.add_argument("--batch-size", type=int, default=96,
                        help="Texts per API call (max 96)")
    args = parser.parse_args()

    print("Semantic Paragraph Alignment (Cohere embed-v4.0)")
    print("=" * 60)

    # Check API key
    api_key = os.getenv("COHERE_API_KEY")
    if not api_key:
        print("ERROR: COHERE_API_KEY not set in .env")
        sys.exit(1)

    co = cohere.Client(api_key=api_key)
    print(f"  Cohere client initialized")
    print(f"  Delay between batches: {args.delay}s")

    # Load volumes
    print("\nLoading English volumes...")
    en_volumes = load_english_volumes()
    if not en_volumes:
        print("ERROR: No English volumes found. Run download_english_corpus.py first.")
        return
    print(f"  Found {len(en_volumes)} volumes")

    print("Loading French volumes...")
    fr_volumes = load_french_volumes()
    if not fr_volumes:
        print("ERROR: No French volumes found. Run download_french_corpus.py first.")
        return
    print(f"  Found {len(fr_volumes)} volumes")

    # ── Phase 1: Collect all paragraphs ──────────────────────────────────

    print("\n--- Phase 1: Split chapters into paragraphs ---")

    # Each entry: (en_paragraphs, fr_paragraphs, volume, chapter, book)
    chapter_data: list[tuple[list[str], list[str], int, str, str]] = []

    for vol_num in sorted(set(en_volumes.keys()) & set(fr_volumes.keys())):
        en_vol = en_volumes[vol_num]
        fr_vol = fr_volumes[vol_num]
        en_chapters = en_vol.get("chapters", [])
        fr_chapters = fr_vol.get("chapters", [])

        for en_ch in en_chapters:
            ch_name = en_ch["chapter"]
            key = (vol_num, ch_name)
            fr_indices = EN_TO_FR_CHAPTER_MAP.get(key)

            if fr_indices is None:
                print(f"  WARNING: No FR mapping for {key}, skipping FR")
                en_paras = split_paragraphs(en_ch["text"])
                chapter_data.append((en_paras, [], vol_num, ch_name,
                                     en_vol.get("book", "Unknown")))
                continue

            fr_texts = []
            for idx in fr_indices:
                if idx < len(fr_chapters):
                    fr_texts.append(fr_chapters[idx].get("text", ""))
            fr_combined = "\n\n".join(fr_texts)

            en_paras = split_paragraphs(en_ch["text"])
            fr_paras = split_paragraphs(fr_combined)

            print(f"  Vol {vol_num}, {ch_name}: "
                  f"EN={len(en_paras)} FR={len(fr_paras)} paragraphs")

            chapter_data.append((en_paras, fr_paras, vol_num, ch_name,
                                 en_vol.get("book", "Unknown")))

    # ── Phase 2: Embed all paragraphs ────────────────────────────────────

    print(f"\n--- Phase 2: Embed paragraphs with Cohere ---")

    # Flatten all paragraphs into one list for efficient batching
    all_en_texts: list[str] = []
    all_fr_texts: list[str] = []
    en_boundaries: list[tuple[int, int]] = []  # (start, end) per chapter
    fr_boundaries: list[tuple[int, int]] = []

    for en_paras, fr_paras, *_ in chapter_data:
        en_start = len(all_en_texts)
        all_en_texts.extend(en_paras)
        en_boundaries.append((en_start, len(all_en_texts)))

        fr_start = len(all_fr_texts)
        all_fr_texts.extend(fr_paras)
        fr_boundaries.append((fr_start, len(all_fr_texts)))

    print(f"  Total EN paragraphs: {len(all_en_texts)}")
    print(f"  Total FR paragraphs: {len(all_fr_texts)}")
    total_calls = ((len(all_en_texts) + args.batch_size - 1) // args.batch_size +
                   (len(all_fr_texts) + args.batch_size - 1) // args.batch_size)
    est_time = total_calls * args.delay
    print(f"  Estimated API calls: {total_calls} (~{est_time:.0f}s)")

    print("\n  Embedding EN paragraphs...")
    en_embeddings = embed_texts(co, all_en_texts, args.batch_size, args.delay, "EN")

    print("  Embedding FR paragraphs...")
    fr_embeddings = embed_texts(co, all_fr_texts, args.batch_size, args.delay, "FR")

    # ── Phase 3: Align per chapter ───────────────────────────────────────

    print(f"\n--- Phase 3: Semantic alignment per chapter ---")

    all_records: list[dict] = []
    alignment_stats: list[dict] = []

    for ch_idx, (en_paras, fr_paras, vol, chapter, book) in enumerate(chapter_data):
        en_start, en_end = en_boundaries[ch_idx]
        fr_start, fr_end = fr_boundaries[ch_idx]

        if not en_paras:
            continue

        if not fr_paras:
            # No FR text available
            for p in en_paras:
                all_records.append({
                    "text": p, "text_fr": "",
                    "volume": vol, "chapter": chapter, "book": book,
                })
            print(f"  Vol {vol}, {chapter}: {len(en_paras)} EN, no FR")
            continue

        # Slice embeddings for this chapter
        ch_en_emb = en_embeddings[en_start:en_end]
        ch_fr_emb = fr_embeddings[fr_start:fr_end]

        # Compute similarity and do FR-primary alignment
        sim = cosine_similarity_matrix(ch_en_emb, ch_fr_emb)
        groups = fr_primary_align(sim)

        en_majority = len(en_paras) >= len(fr_paras)
        output_count = min(len(en_paras), len(fr_paras))

        # Compute alignment quality metrics
        sims = []
        records = []
        for src_indices, tgt_idx in groups:
            if en_majority:
                # EN grouped, each group → 1 FR paragraph
                en_text = "\n\n".join(en_paras[i] for i in src_indices)
                fr_text = fr_paras[tgt_idx]
                # Average similarity of the group
                group_sims = [sim[i][tgt_idx] for i in src_indices]
            else:
                # FR grouped, each group → 1 EN paragraph
                en_text = en_paras[tgt_idx]
                fr_text = "\n\n".join(fr_paras[i] for i in src_indices)
                group_sims = [sim[tgt_idx][i] for i in src_indices]

            sims.append(float(np.mean(group_sims)))
            records.append({
                "text": en_text,
                "text_fr": fr_text,
                "volume": vol,
                "chapter": chapter,
                "book": book,
            })

        avg_sim = np.mean(sims) if sims else 0.0
        min_sim = np.min(sims) if sims else 0.0

        stats = {
            "volume": vol, "chapter": chapter,
            "en_count": len(en_paras), "fr_count": len(fr_paras),
            "output_count": output_count,
            "en_majority": en_majority,
            "avg_similarity": round(float(avg_sim), 3),
            "min_similarity": round(float(min_sim), 3),
        }
        alignment_stats.append(stats)

        majority_label = "EN>FR" if en_majority else "FR>EN"
        quality = "OK" if avg_sim > 0.7 else "REVIEW" if avg_sim > 0.5 else "POOR"
        print(f"  Vol {vol}, {chapter}: {majority_label} "
              f"avg_sim={avg_sim:.3f} min={min_sim:.3f} "
              f"output={output_count} [{quality}]")

        all_records.extend(records)

    # ── Save output ──────────────────────────────────────────────────────

    print(f"\n{'=' * 60}")
    print(f"Total aligned paragraph pairs: {len(all_records)}")
    has_fr = sum(1 for r in all_records if r["text_fr"])
    print(f"With French text: {has_fr}/{len(all_records)} "
          f"({has_fr / len(all_records) * 100:.1f}%)")

    # Overall stats
    all_avg_sims = [s["avg_similarity"] for s in alignment_stats]
    if all_avg_sims:
        print(f"Overall avg similarity: {np.mean(all_avg_sims):.3f}")
        print(f"Lowest chapter avg: {min(all_avg_sims):.3f}")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to: {OUTPUT_PATH}")

    # Save alignment stats for review
    stats_path = DATA_DIR / "alignment_stats.json"
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(alignment_stats, f, indent=2)
    print(f"Stats saved to: {stats_path}")

    # Check first paragraph
    if all_records:
        first = all_records[0]
        print(f"\nFirst EN: {first['text'][:80]}...")
        print(f"First FR: {first['text_fr'][:80]}...")

    # Per-volume summary
    print(f"\n=== Per-Volume Summary ===")
    vol_counts = Counter(r["volume"] for r in all_records)
    for vol in sorted(vol_counts):
        vol_stats = [s for s in alignment_stats if s["volume"] == vol]
        avg = np.mean([s["avg_similarity"] for s in vol_stats]) if vol_stats else 0
        print(f"  Vol {vol}: {vol_counts[vol]} pairs, avg_sim={avg:.3f}")

    print(f"\nNext step: run chunk_bilingual.py to produce parsed_clean_bilingual.json")


if __name__ == "__main__":
    main()
