#!/usr/bin/env python3
"""
Sanitize and re-chunk Proust passages from parsed.json.

Reads parsed.json, applies text fixes, removes title/credit passages,
merges short passages, splits long passages, and outputs parsed_clean.json.

Usage:
    cd backend
    python scripts/sanitize_passages.py
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
LONG_THRESHOLD = 1500   # chars — split passages longer than this
TARGET_CHUNK = 700      # chars — target size when splitting
MIN_SPLIT = 200         # chars — don't create splits smaller than this

# Sentence boundary regex: split after sentence-ending punctuation
# (optionally followed by a closing quote) before a capital letter or opening quote.
SENTENCE_SPLIT_RE = re.compile(
    r'(?<=[.?!])\s+(?=[A-Z\u201c"])'
    r'|(?<=[.?!]\u201d)\s+(?=[A-Z\u201c"])'
    r'|(?<=[.?!]")\s+(?=[A-Z\u201c"])'
)


def load_passages(filepath: Path) -> list[dict]:
    """Load passages from JSON file."""
    print(f"Loading: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"  Loaded {len(data)} passages")
    return data


def step_clean_text(passages: list[dict]) -> int:
    """Apply text cleaning to all passages. Returns count of passages modified."""
    fixed = 0
    for p in passages:
        original = p.get("text", "")
        cleaned = clean_passage_text(original)
        if cleaned != original:
            p["text"] = cleaned
            fixed += 1
    return fixed


def step_remove_title_passages(passages: list[dict]) -> tuple[list[dict], int]:
    """Remove passages where chapter is None (title/credit lines)."""
    kept = [p for p in passages if p.get("chapter") is not None]
    removed = len(passages) - len(kept)
    return kept, removed


def _ends_mid_sentence(text: str) -> bool:
    """Check if text ends mid-sentence (no terminal punctuation)."""
    stripped = text.rstrip()
    if not stripped:
        return False
    return stripped[-1] not in ".?!\u201d\u201c\"'"


def _starts_continuation(text: str) -> bool:
    """Check if text starts as a continuation (lowercase or punctuation)."""
    stripped = text.lstrip()
    if not stripped:
        return False
    return stripped[0].islower() or stripped[0] in ",;:—"


def step_merge_short(passages: list[dict]) -> tuple[list[dict], int]:
    """
    Merge short passages (< SHORT_THRESHOLD chars) with neighbors.
    Never merge across chapter or book boundaries.
    Run multiple passes until stable.
    """
    total_merges = 0
    changed = True
    max_passes = 20  # safety limit

    while changed and max_passes > 0:
        changed = False
        max_passes -= 1
        result = []
        skip_next = False

        for i, p in enumerate(passages):
            if skip_next:
                skip_next = False
                continue

            text = p.get("text", "").strip()

            if len(text) < SHORT_THRESHOLD:
                book = p.get("book")
                chapter = p.get("chapter")

                # Try merging with previous (same chapter/book)
                if result:
                    prev = result[-1]
                    if prev.get("book") == book and prev.get("chapter") == chapter:
                        prev["text"] = prev["text"].rstrip() + " " + text.lstrip()
                        total_merges += 1
                        changed = True
                        continue

                # Try merging with next (same chapter/book)
                if i + 1 < len(passages):
                    nxt = passages[i + 1]
                    if nxt.get("book") == book and nxt.get("chapter") == chapter:
                        nxt["text"] = text.rstrip() + " " + nxt.get("text", "").lstrip()
                        total_merges += 1
                        changed = True
                        # Skip current passage — its text is now in the next passage
                        continue

            result.append(p)

        passages = result

    return passages, total_merges


def step_split_long(passages: list[dict]) -> tuple[list[dict], int]:
    """
    Split passages longer than LONG_THRESHOLD at sentence boundaries.
    Target ~TARGET_CHUNK chars per chunk. Don't create chunks under MIN_SPLIT.
    """
    result = []
    split_count = 0

    for p in passages:
        text = p.get("text", "")

        if len(text) <= LONG_THRESHOLD:
            result.append(p)
            continue

        # Split at sentence boundaries
        sentences = SENTENCE_SPLIT_RE.split(text)

        if len(sentences) <= 1:
            # Can't split — no sentence boundaries found
            result.append(p)
            continue

        # Group sentences into chunks of ~TARGET_CHUNK
        chunks = []
        current_chunk = ""

        for sent in sentences:
            if current_chunk and len(current_chunk) + len(sent) > TARGET_CHUNK:
                chunks.append(current_chunk.strip())
                current_chunk = sent
            else:
                current_chunk = (current_chunk + " " + sent).strip() if current_chunk else sent

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        # Merge any trailing runt chunk back into the previous one
        if len(chunks) > 1 and len(chunks[-1]) < MIN_SPLIT:
            chunks[-2] = chunks[-2] + " " + chunks[-1]
            chunks.pop()

        # Merge any leading runt chunk into the next one
        if len(chunks) > 1 and len(chunks[0]) < MIN_SPLIT:
            chunks[1] = chunks[0] + " " + chunks[1]
            chunks.pop(0)

        if len(chunks) <= 1:
            result.append(p)
            continue

        # Create new passages from chunks
        split_count += 1
        for chunk_text in chunks:
            new_p = {
                "book": p.get("book"),
                "volume": p.get("volume"),
                "chapter": p.get("chapter"),
                "text": chunk_text,
            }
            result.append(new_p)

    return result, split_count


def step_reindex(passages: list[dict], original_passages: list[dict]) -> list[dict]:
    """Re-index passages sequentially from 1. Keep original_index for traceability."""
    for i, p in enumerate(passages, start=1):
        if "index" in p:
            p["original_index"] = p["index"]
        p["index"] = i
    return passages


def compute_stats(passages: list[dict]) -> dict:
    """Compute statistics about passage lengths."""
    lengths = [len(p.get("text", "")) for p in passages]
    word_counts = [len(p.get("text", "").split()) for p in passages]

    under_50 = sum(1 for l in lengths if l < 50)
    under_100 = sum(1 for l in lengths if l < 100)
    over_1500 = sum(1 for l in lengths if l > 1500)
    over_2500 = sum(1 for l in lengths if l > 2500)

    return {
        "count": len(passages),
        "total_words": sum(word_counts),
        "avg_chars": round(sum(lengths) / len(lengths)) if lengths else 0,
        "min_chars": min(lengths) if lengths else 0,
        "max_chars": max(lengths) if lengths else 0,
        "under_50": under_50,
        "under_100": under_100,
        "over_1500": over_1500,
        "over_2500": over_2500,
    }


def count_carets(passages: list[dict]) -> int:
    """Count remaining ^ characters."""
    return sum(p.get("text", "").count("^") for p in passages)


def main():
    backend_dir = Path(__file__).parent.parent
    input_file = backend_dir / "parsed.json"
    output_file = backend_dir / "parsed_clean.json"

    if not input_file.exists():
        print(f"ERROR: {input_file} not found")
        sys.exit(1)

    # Load
    original = load_passages(input_file)
    passages = json.loads(json.dumps(original))  # deep copy

    before_stats = compute_stats(passages)
    carets_before = count_carets(passages)

    print(f"\n=== Before Sanitization ===")
    print(f"  Passages:    {before_stats['count']}")
    print(f"  Total words: {before_stats['total_words']}")
    print(f"  Avg chars:   {before_stats['avg_chars']}")
    print(f"  Min chars:   {before_stats['min_chars']}")
    print(f"  Max chars:   {before_stats['max_chars']}")
    print(f"  Under 50ch:  {before_stats['under_50']}")
    print(f"  Under 100ch: {before_stats['under_100']}")
    print(f"  Over 1500ch: {before_stats['over_1500']}")
    print(f"  Over 2500ch: {before_stats['over_2500']}")
    print(f"  Caret (^):   {carets_before}")

    # Step 1: Clean text
    print(f"\n--- Step 1: Clean text artifacts ---")
    text_fixes = step_clean_text(passages)
    print(f"  Fixed {text_fixes} passages")

    # Step 2: Remove title/credit passages
    print(f"\n--- Step 2: Remove title/credit passages ---")
    passages, removed = step_remove_title_passages(passages)
    print(f"  Removed {removed} passages (chapter=null)")

    # Step 3: Merge short passages
    print(f"\n--- Step 3: Merge short passages ---")
    passages, merges = step_merge_short(passages)
    print(f"  Merged {merges} times → {len(passages)} passages")

    # Step 4: Split long passages
    print(f"\n--- Step 4: Split long passages ---")
    passages, splits = step_split_long(passages)
    print(f"  Split {splits} passages → {len(passages)} passages")

    # Step 5: Re-index
    print(f"\n--- Step 5: Re-index ---")
    passages = step_reindex(passages, original)
    print(f"  Re-indexed {len(passages)} passages (1..{len(passages)})")

    # Stats
    after_stats = compute_stats(passages)
    carets_after = count_carets(passages)

    print(f"\n=== After Sanitization ===")
    print(f"  Passages:    {after_stats['count']}")
    print(f"  Total words: {after_stats['total_words']}")
    print(f"  Avg chars:   {after_stats['avg_chars']}")
    print(f"  Min chars:   {after_stats['min_chars']}")
    print(f"  Max chars:   {after_stats['max_chars']}")
    print(f"  Under 50ch:  {after_stats['under_50']}")
    print(f"  Under 100ch: {after_stats['under_100']}")
    print(f"  Over 1500ch: {after_stats['over_1500']}")
    print(f"  Over 2500ch: {after_stats['over_2500']}")
    print(f"  Caret (^):   {carets_after}")

    print(f"\n=== Changes ===")
    print(f"  Passages: {before_stats['count']} → {after_stats['count']} ({after_stats['count'] - before_stats['count']:+d})")
    print(f"  Words:    {before_stats['total_words']} → {after_stats['total_words']} ({after_stats['total_words'] - before_stats['total_words']:+d})")
    print(f"  Carets:   {carets_before} → {carets_after}")

    # Verify opening line
    if passages:
        first_text = passages[0].get("text", "")
        if "For a long time I used to go to bed early" in first_text:
            print(f"\n  ✓ Opening line intact")
        else:
            print(f"\n  ✗ WARNING: Opening line may be wrong: {first_text[:80]}...")

    # Save
    print(f"\nSaving to {output_file}...")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(passages, f, indent=2, ensure_ascii=False)

    print(f"Done! Saved {len(passages)} passages to {output_file}")


if __name__ == "__main__":
    main()
