#!/usr/bin/env python3
"""
Bilingual co-chunking: take aligned paragraph pairs and produce
parsed_clean_bilingual.json with both English and French text per passage.

Applies the same merge/split rules as sanitize_passages.py but co-chunks
both languages together so they stay aligned.

Usage:
    cd backend
    python scripts/chunk_bilingual.py
"""

import json
import re
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from text_utils import clean_passage_text

# Thresholds
SHORT_THRESHOLD = 100   # chars — merge passages shorter than this
LONG_THRESHOLD = 2000   # chars — split passages longer than this
TARGET_CHUNK = 1000     # chars — target size when splitting
MIN_SPLIT = 200         # chars — don't create splits smaller than this

# Sentence boundary regex for English
EN_SENTENCE_SPLIT = re.compile(
    r'(?<=[.?!])\s+(?=[A-Z\u201c"])'
    r'|(?<=[.?!]\u201d)\s+(?=[A-Z\u201c"])'
    r'|(?<=[.?!]")\s+(?=[A-Z\u201c"])'
)

# Sentence boundary regex for French
FR_SENTENCE_SPLIT = re.compile(
    r'(?<=[.?!])\s+(?=[A-Z\u00c0-\u00dc\u00ab\u201c])'
    r'|(?<=[.?!\u00bb])\s+(?=[A-Z\u00c0-\u00dc])'
)

DATA_DIR = Path(__file__).parent.parent / "data"
INPUT_PATH = DATA_DIR / "aligned_paragraphs.json"
OUTPUT_PATH = Path(__file__).parent.parent / "parsed_clean_bilingual.json"


def split_sentences_en(text: str) -> list[str]:
    """Split English text at sentence boundaries."""
    return EN_SENTENCE_SPLIT.split(text)


def split_sentences_fr(text: str) -> list[str]:
    """Split French text at sentence boundaries."""
    return FR_SENTENCE_SPLIT.split(text)


def proportional_split(
    text: str,
    reference_chunks: list[str],
    sentence_splitter=None,
) -> list[str]:
    """Split text proportionally to match reference chunk boundaries.

    When the reference side has been split into N chunks, split this text
    at sentence boundaries proportional to the reference chunk character ratios.
    Empty chunks are backfilled from neighbors.

    Args:
        text: The text to split.
        reference_chunks: Chunks from the other language to match proportionally.
        sentence_splitter: Function to split text into sentences.
                          Defaults to split_sentences_fr.
    """
    if sentence_splitter is None:
        sentence_splitter = split_sentences_fr

    if not text or not reference_chunks or len(reference_chunks) <= 1:
        return [text] if text else [""]

    sentences = sentence_splitter(text)
    if len(sentences) < len(reference_chunks):
        # Fewer sentences than chunks — distribute one sentence per chunk,
        # and duplicate the nearest sentence for any remaining chunks
        result = []
        for i in range(len(reference_chunks)):
            idx = round(i * (len(sentences) - 1) / max(len(reference_chunks) - 1, 1))
            idx = min(idx, len(sentences) - 1)
            result.append(sentences[idx])
        return result

    # Calculate split points based on reference cumulative character positions
    ref_total = sum(len(c) for c in reference_chunks)
    ref_cumulative = []
    running = 0
    for chunk in reference_chunks:
        running += len(chunk)
        ref_cumulative.append(running / ref_total)

    # Map sentences to chunks
    text_total = len(text)
    text_cumulative = 0
    chunk_bins: list[list[str]] = [[] for _ in reference_chunks]
    chunk_idx = 0

    for sent in sentences:
        text_cumulative += len(sent) + 1  # +1 for space
        position = text_cumulative / text_total

        while chunk_idx < len(reference_chunks) - 1 and position > ref_cumulative[chunk_idx]:
            chunk_idx += 1

        chunk_bins[chunk_idx].append(sent)

    # Backfill any empty chunks from neighbors
    result = [" ".join(sents) for sents in chunk_bins]
    for i in range(len(result)):
        if not result[i].strip():
            if i > 0 and result[i - 1].strip():
                result[i] = result[i - 1]
            elif i + 1 < len(result) and result[i + 1].strip():
                result[i] = result[i + 1]

    return result


def proportional_split_fr(fr_text: str, en_splits: list[str], en_total: int) -> list[str]:
    """Split French text proportionally to match English split boundaries.

    Backward-compatible wrapper around proportional_split().
    """
    return proportional_split(fr_text, en_splits, split_sentences_fr)


def step_clean(records: list[dict]) -> int:
    """Apply text cleaning to both EN and FR text. Returns count modified."""
    fixed = 0
    for r in records:
        en_orig = r.get("text", "")
        en_clean = clean_passage_text(en_orig)
        if en_clean != en_orig:
            r["text"] = en_clean
            fixed += 1

        # Clean FR text: normalize whitespace, strip
        fr_text = r.get("text_fr", "")
        if fr_text:
            fr_clean = re.sub(r"[ \t]+", " ", fr_text).strip()
            # Normalize non-breaking spaces around French punctuation
            fr_clean = fr_clean.replace("\u00a0", "\u00a0")  # keep nbsp
            if fr_clean != fr_text:
                r["text_fr"] = fr_clean
    return fixed


def step_merge_short(records: list[dict]) -> tuple[list[dict], int]:
    """Merge short passages (< SHORT_THRESHOLD EN chars) with neighbors.

    Both EN and FR text are merged together to stay aligned.
    Never merges across chapter/book boundaries.
    """
    total_merges = 0
    changed = True
    max_passes = 20

    while changed and max_passes > 0:
        changed = False
        max_passes -= 1
        result = []

        for i, r in enumerate(records):
            text = r.get("text", "").strip()

            if len(text) < SHORT_THRESHOLD:
                book = r.get("book")
                chapter = r.get("chapter")

                # Try merging with previous (same chapter/book)
                if result:
                    prev = result[-1]
                    if prev.get("book") == book and prev.get("chapter") == chapter:
                        prev["text"] = prev["text"].rstrip() + " " + text.lstrip()
                        # Merge FR too
                        prev_fr = prev.get("text_fr", "")
                        cur_fr = r.get("text_fr", "")
                        if prev_fr and cur_fr:
                            prev["text_fr"] = prev_fr.rstrip() + " " + cur_fr.lstrip()
                        elif cur_fr:
                            prev["text_fr"] = cur_fr
                        total_merges += 1
                        changed = True
                        continue

                # Try merging with next (same chapter/book)
                if i + 1 < len(records):
                    nxt = records[i + 1]
                    if nxt.get("book") == book and nxt.get("chapter") == chapter:
                        nxt["text"] = text.rstrip() + " " + nxt.get("text", "").lstrip()
                        # Merge FR too
                        nxt_fr = nxt.get("text_fr", "")
                        cur_fr = r.get("text_fr", "")
                        if cur_fr and nxt_fr:
                            nxt["text_fr"] = cur_fr.rstrip() + " " + nxt_fr.lstrip()
                        elif cur_fr:
                            nxt["text_fr"] = cur_fr
                        total_merges += 1
                        changed = True
                        continue

            result.append(r)

        records = result

    return records, total_merges


def step_split_paragraphs(records: list[dict]) -> tuple[list[dict], int]:
    """Split records at paragraph boundaries (\n\n) before sentence splitting.

    After FR-primary alignment, one side may contain multiple concatenated
    paragraphs (joined with \n\n). This step splits at those natural boundaries
    first, grouping sub-paragraphs into chunks of ~TARGET_CHUNK chars.
    The other side (single paragraph) is split proportionally at sentence
    boundaries.

    Records without \n\n pass through unchanged.
    """
    result = []
    split_count = 0

    for r in records:
        en_text = r.get("text", "")
        fr_text = r.get("text_fr", "")

        en_has_paras = "\n\n" in en_text
        fr_has_paras = "\n\n" in fr_text

        if not en_has_paras and not fr_has_paras:
            result.append(r)
            continue

        # Determine which side has multiple paragraphs
        if en_has_paras:
            multi_paras = [p.strip() for p in en_text.split("\n\n") if p.strip()]
            single_text = fr_text.replace("\n\n", " ")
            multi_is_en = True
            single_splitter = split_sentences_fr
        else:
            multi_paras = [p.strip() for p in fr_text.split("\n\n") if p.strip()]
            single_text = en_text.replace("\n\n", " ")
            multi_is_en = False
            single_splitter = split_sentences_en

        if len(multi_paras) <= 1:
            # Only one paragraph after splitting — clean up \n\n and pass through
            r["text"] = en_text.replace("\n\n", " ")
            r["text_fr"] = fr_text.replace("\n\n", " ")
            result.append(r)
            continue

        # Group sub-paragraphs into chunks of ~TARGET_CHUNK chars
        multi_chunks = []
        current_chunk = ""
        for para in multi_paras:
            if current_chunk and len(current_chunk) + len(para) > TARGET_CHUNK:
                multi_chunks.append(current_chunk)
                current_chunk = para
            else:
                current_chunk = (current_chunk + " " + para) if current_chunk else para
        if current_chunk:
            multi_chunks.append(current_chunk)

        # Merge runt chunks
        if len(multi_chunks) > 1 and len(multi_chunks[-1]) < MIN_SPLIT:
            multi_chunks[-2] = multi_chunks[-2] + " " + multi_chunks[-1]
            multi_chunks.pop()
        if len(multi_chunks) > 1 and len(multi_chunks[0]) < MIN_SPLIT:
            multi_chunks[1] = multi_chunks[0] + " " + multi_chunks[1]
            multi_chunks.pop(0)

        if len(multi_chunks) <= 1:
            # Everything merged into one chunk — clean up \n\n
            r["text"] = en_text.replace("\n\n", " ")
            r["text_fr"] = fr_text.replace("\n\n", " ")
            result.append(r)
            continue

        # Split the single-text side proportionally
        single_chunks = proportional_split(
            single_text, multi_chunks, single_splitter
        )

        split_count += 1
        for i, multi_chunk in enumerate(multi_chunks):
            single_chunk = single_chunks[i] if i < len(single_chunks) else ""
            if multi_is_en:
                en_chunk, fr_chunk = multi_chunk, single_chunk
            else:
                en_chunk, fr_chunk = single_chunk, multi_chunk

            result.append({
                "book": r.get("book"),
                "volume": r.get("volume"),
                "chapter": r.get("chapter"),
                "text": en_chunk,
                "text_fr": fr_chunk,
            })

    return result, split_count


def step_split_long(records: list[dict]) -> tuple[list[dict], int]:
    """Split passages longer than LONG_THRESHOLD at sentence boundaries.

    Both EN and FR text are split proportionally.
    """
    result = []
    split_count = 0

    for r in records:
        en_text = r.get("text", "")
        fr_text = r.get("text_fr", "")

        if len(en_text) <= LONG_THRESHOLD:
            result.append(r)
            continue

        # Split EN at sentence boundaries
        en_sentences = split_sentences_en(en_text)
        if len(en_sentences) <= 1:
            result.append(r)
            continue

        # Group EN sentences into chunks of ~TARGET_CHUNK
        en_chunks = []
        current_chunk = ""
        for sent in en_sentences:
            if current_chunk and len(current_chunk) + len(sent) > TARGET_CHUNK:
                en_chunks.append(current_chunk.strip())
                current_chunk = sent
            else:
                current_chunk = (current_chunk + " " + sent).strip() if current_chunk else sent
        if current_chunk.strip():
            en_chunks.append(current_chunk.strip())

        # Merge runt chunks
        if len(en_chunks) > 1 and len(en_chunks[-1]) < MIN_SPLIT:
            en_chunks[-2] = en_chunks[-2] + " " + en_chunks[-1]
            en_chunks.pop()
        if len(en_chunks) > 1 and len(en_chunks[0]) < MIN_SPLIT:
            en_chunks[1] = en_chunks[0] + " " + en_chunks[1]
            en_chunks.pop(0)

        if len(en_chunks) <= 1:
            result.append(r)
            continue

        # Split FR proportionally
        fr_chunks = proportional_split_fr(fr_text, en_chunks, len(en_text))

        split_count += 1
        for en_chunk, fr_chunk in zip(en_chunks, fr_chunks):
            result.append({
                "book": r.get("book"),
                "volume": r.get("volume"),
                "chapter": r.get("chapter"),
                "text": en_chunk,
                "text_fr": fr_chunk,
            })

    return result, split_count


def step_reindex(records: list[dict]) -> list[dict]:
    """Re-index passages sequentially from 1."""
    for i, r in enumerate(records, start=1):
        r["index"] = i
    return records


def compute_stats(records: list[dict]) -> dict:
    """Compute statistics about passage lengths."""
    en_lengths = [len(r.get("text", "")) for r in records]
    fr_lengths = [len(r.get("text_fr", "")) for r in records if r.get("text_fr")]

    return {
        "count": len(records),
        "en_avg": round(sum(en_lengths) / len(en_lengths)) if en_lengths else 0,
        "en_min": min(en_lengths) if en_lengths else 0,
        "en_max": max(en_lengths) if en_lengths else 0,
        "fr_count": len(fr_lengths),
        "fr_avg": round(sum(fr_lengths) / len(fr_lengths)) if fr_lengths else 0,
        "under_100": sum(1 for l in en_lengths if l < 100),
        "over_2000": sum(1 for l in en_lengths if l > 2000),
    }


def main():
    print("Bilingual Co-Chunking")
    print("=" * 60)

    if not INPUT_PATH.exists():
        print(f"ERROR: {INPUT_PATH} not found")
        print("Run align_paragraphs.py first.")
        sys.exit(1)

    # Load aligned paragraphs
    print(f"\nLoading: {INPUT_PATH}")
    with open(INPUT_PATH, encoding="utf-8") as f:
        records = json.load(f)
    print(f"  Loaded {len(records)} aligned paragraph pairs")

    before_stats = compute_stats(records)
    print(f"\n=== Before Chunking ===")
    print(f"  Records:     {before_stats['count']}")
    print(f"  EN avg/min/max: {before_stats['en_avg']}/{before_stats['en_min']}/{before_stats['en_max']}")
    print(f"  FR coverage: {before_stats['fr_count']}")
    print(f"  Under 100ch: {before_stats['under_100']}")
    print(f"  Over 2000ch: {before_stats['over_2000']}")

    # Step 1: Clean text
    print(f"\n--- Step 1: Clean text ---")
    fixed = step_clean(records)
    print(f"  Cleaned {fixed} passages")

    # Step 2: Merge short passages
    print(f"\n--- Step 2: Merge short passages ---")
    records, merges = step_merge_short(records)
    print(f"  Merged {merges} times -> {len(records)} passages")

    # Step 3: Split at paragraph boundaries
    print(f"\n--- Step 3: Split at paragraph boundaries ---")
    records, para_splits = step_split_paragraphs(records)
    print(f"  Split {para_splits} passages at paragraph boundaries -> {len(records)} passages")

    # Step 4: Split remaining long passages at sentence boundaries
    print(f"\n--- Step 4: Split long passages ---")
    records, splits = step_split_long(records)
    print(f"  Split {splits} passages -> {len(records)} passages")

    # Step 5: Re-index
    print(f"\n--- Step 5: Re-index ---")
    records = step_reindex(records)
    print(f"  Re-indexed {len(records)} passages (1..{len(records)})")

    # Stats
    after_stats = compute_stats(records)
    print(f"\n=== After Chunking ===")
    print(f"  Records:     {after_stats['count']}")
    print(f"  EN avg/min/max: {after_stats['en_avg']}/{after_stats['en_min']}/{after_stats['en_max']}")
    print(f"  FR coverage: {after_stats['fr_count']}")
    print(f"  Under 100ch: {after_stats['under_100']}")
    print(f"  Over 2000ch: {after_stats['over_2000']}")

    # Verify opening line
    if records:
        first = records[0]
        en_start = first.get("text", "")[:80]
        fr_start = first.get("text_fr", "")[:80]
        if "long time" in en_start.lower() or "bed early" in en_start.lower():
            print(f"\n  OK: EN opening: {en_start}...")
        else:
            print(f"\n  WARNING: EN opening may be wrong: {en_start}...")
        if "longtemps" in fr_start.lower():
            print(f"  OK: FR opening: {fr_start}...")
        else:
            print(f"  WARNING: FR opening may be wrong: {fr_start}...")

    # Save
    print(f"\nSaving to {OUTPUT_PATH}...")
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    print(f"Done! Saved {len(records)} bilingual passages to {OUTPUT_PATH}")

    # Per-volume summary
    print(f"\n=== Per-Volume Summary ===")
    from collections import Counter
    vol_counts = Counter(r.get("volume") for r in records)
    for vol in sorted(vol_counts):
        print(f"  Vol {vol}: {vol_counts[vol]} passages")


if __name__ == "__main__":
    main()
