"""
Align French text with English passages using chapter-level proportional alignment.

For each English passage (chunk), this script:
1. Identifies its volume and chapter
2. Finds the corresponding French chapter text
3. Calculates the passage's proportional position within the English chapter
4. Extracts the corresponding proportional segment of French text,
   snapping to sentence boundaries

This is approximate but sufficient for a reading toggle since the reading view
merges consecutive chunks into paragraphs.

Usage:
    cd backend
    python scripts/align_french_text.py
"""

import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
FRENCH_DIR = DATA_DIR / "french_raw"
PARSED_PATH = Path(__file__).parent.parent / "parsed_clean.json"
OUTPUT_PATH = DATA_DIR / "french_aligned.json"

# ── Chapter name mapping ────────────────────────────────────────────────────
# Maps English chapter names to French chapter names/subpage names.
# This needs to be populated based on the actual content of both corpora.
# We'll build this dynamically by matching chapter positions within volumes.


def split_sentences(text: str) -> list[str]:
    """Split French text into sentences."""
    # French sentence boundaries: .!? followed by space and uppercase, or end of text
    # Handle abbreviations like M., Mme., etc.
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-ZÀ-ÿ«])', text)
    return [s.strip() for s in sentences if s.strip()]


def load_english_corpus() -> list[dict]:
    """Load the English parsed corpus."""
    with open(PARSED_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_french_volumes() -> dict[int, dict]:
    """Load all downloaded French volumes. Returns {volume_num: volume_data}."""
    french = {}
    for vol_file in sorted(FRENCH_DIR.glob("volume_*.json")):
        with open(vol_file, encoding="utf-8") as f:
            data = json.load(f)
            french[data["volume"]] = data
    return french


def build_english_chapter_map(passages: list[dict]) -> dict[tuple[int, str], list[dict]]:
    """Group English passages by (volume, chapter)."""
    chapters: dict[tuple[int, str], list[dict]] = {}
    for p in passages:
        vol = p.get("volume", 1)
        ch = p.get("chapter", "Unknown")
        key = (vol, ch)
        if key not in chapters:
            chapters[key] = []
        chapters[key].append(p)
    return chapters


def match_chapters(
    en_chapters: list[str],
    fr_chapters: list[dict],
) -> list[tuple[str, dict | None]]:
    """
    Match English chapters to French chapters by position within the volume.

    Uses positional matching since chapter names differ between languages.
    When there are more French chapters than English ones, French chapters
    are merged proportionally (e.g. 3 FR chapters -> 2 EN chapters means
    the first EN chapter gets FR chapters 1+first half of 2, etc.).
    For simplicity, we concatenate extra French chapters into the last
    English chapter when counts don't match.

    Returns list of (en_chapter_name, fr_chapter_data_or_None).
    """
    n_en = len(en_chapters)
    n_fr = len(fr_chapters)

    if n_en == 0:
        return []

    if n_en >= n_fr:
        # 1:1 or more EN than FR
        matches = []
        for i, en_ch in enumerate(en_chapters):
            if i < n_fr:
                matches.append((en_ch, fr_chapters[i]))
            else:
                matches.append((en_ch, None))
        return matches

    # More FR chapters than EN: distribute FR chapters across EN chapters
    # Use proportional distribution based on French text lengths
    fr_lengths = [len(ch.get("text", "")) for ch in fr_chapters]
    total_fr_len = sum(fr_lengths)

    # Calculate cumulative positions for French chapters
    cumulative = []
    running = 0
    for length in fr_lengths:
        cumulative.append(running)
        running += length

    matches = []
    for i, en_ch in enumerate(en_chapters):
        # This EN chapter spans from i/n_en to (i+1)/n_en of the total FR text
        start_frac = i / n_en
        end_frac = (i + 1) / n_en
        start_char = int(start_frac * total_fr_len)
        end_char = int(end_frac * total_fr_len)

        # Find which FR chapters fall in this range and merge their text
        merged_text = []
        for j, fr_ch in enumerate(fr_chapters):
            ch_start = cumulative[j]
            ch_end = ch_start + fr_lengths[j]
            # Include this FR chapter if it overlaps with our range
            if ch_end > start_char and ch_start < end_char:
                merged_text.append(fr_ch.get("text", ""))

        merged_chapter = {
            "text": "\n\n".join(merged_text),
            "chapter": f"merged_{i}",
        }
        matches.append((en_ch, merged_chapter))

    return matches


def align_passage_to_french(
    passage_position: float,  # 0.0 to 1.0 within chapter
    passage_length_ratio: float,  # Fraction of chapter this passage represents
    french_text: str,
    french_sentences: list[str],
) -> str:
    """
    Extract the proportional segment of French text corresponding to
    an English passage's position in its chapter.
    """
    if not french_sentences:
        return ""

    total_chars = len(french_text)
    if total_chars == 0:
        return ""

    # Calculate target character range in French text
    start_char = int(passage_position * total_chars)
    end_char = int((passage_position + passage_length_ratio) * total_chars)

    # Snap to sentence boundaries
    cumulative = 0
    start_sentence = 0
    end_sentence = len(french_sentences)

    for i, sent in enumerate(french_sentences):
        sent_end = cumulative + len(sent)
        if cumulative <= start_char < sent_end:
            start_sentence = i
        if cumulative <= end_char <= sent_end:
            end_sentence = i + 1
            break
        cumulative = sent_end + 1  # +1 for space

    # Extract sentences
    selected = french_sentences[start_sentence:end_sentence]
    return " ".join(selected)


def align_volume(
    volume_num: int,
    en_chapter_map: dict[tuple[int, str], list[dict]],
    french_volume: dict,
    en_chapter_order: list[str],
) -> dict[int, str]:
    """
    Align all English passages in a volume with French text.

    Returns {passage_index: french_text}.
    """
    aligned: dict[int, str] = {}

    # Use document-order chapter list (not sorted alphabetically)
    en_chapters = en_chapter_order

    if not en_chapters:
        print(f"  No English chapters found for volume {volume_num}")
        return aligned

    fr_chapters = french_volume.get("chapters", [])
    if not fr_chapters:
        print(f"  No French chapters found for volume {volume_num}")
        return aligned

    # Match chapters by position
    matches = match_chapters(en_chapters, fr_chapters)
    print(f"  Matched {sum(1 for _, fr in matches if fr)} / {len(en_chapters)} chapters")

    for en_ch_name, fr_ch_data in matches:
        key = (volume_num, en_ch_name)
        en_passages = en_chapter_map.get(key, [])

        if not en_passages or fr_ch_data is None:
            continue

        french_text = fr_ch_data["text"]
        french_sentences = split_sentences(french_text)

        # Calculate total English chapter text length
        total_en_chars = sum(len(p.get("text", "")) for p in en_passages)
        if total_en_chars == 0:
            continue

        cumulative_en_chars = 0
        for p in en_passages:
            passage_text = p.get("text", "")
            passage_len = len(passage_text)

            # Position and length as fraction of chapter
            position = cumulative_en_chars / total_en_chars
            length_ratio = passage_len / total_en_chars

            # Align to French
            fr_text = align_passage_to_french(
                position, length_ratio, french_text, french_sentences
            )

            passage_index = p.get("index")
            if passage_index is not None and fr_text:
                aligned[passage_index] = fr_text

            cumulative_en_chars += passage_len

    return aligned


def main():
    print("Aligning French text with English passages...")
    print()

    # Load corpora
    print("Loading English corpus...")
    en_passages = load_english_corpus()
    print(f"  {len(en_passages)} passages")

    print("Loading French volumes...")
    french_volumes = load_french_volumes()
    print(f"  {len(french_volumes)} volumes found")

    if not french_volumes:
        print("\nNo French volumes found. Run download_french_corpus.py first.")
        return

    # Build chapter map
    en_chapter_map = build_english_chapter_map(en_passages)
    print(f"  {len(en_chapter_map)} unique chapters")

    # Build document-order chapter lists per volume from the original passages
    en_chapter_order_by_vol: dict[int, list[str]] = {}
    for p in en_passages:
        vol = p.get("volume", 1)
        ch = p.get("chapter", "Unknown")
        if vol not in en_chapter_order_by_vol:
            en_chapter_order_by_vol[vol] = []
        if ch not in en_chapter_order_by_vol[vol]:
            en_chapter_order_by_vol[vol].append(ch)

    # Align each volume
    all_aligned: dict[int, str] = {}
    for vol_num in sorted(french_volumes.keys()):
        print(f"\nVolume {vol_num}: {french_volumes[vol_num]['title_fr']}")
        chapter_order = en_chapter_order_by_vol.get(vol_num, [])
        vol_aligned = align_volume(
            vol_num, en_chapter_map, french_volumes[vol_num], chapter_order
        )
        all_aligned.update(vol_aligned)
        print(f"  Aligned {len(vol_aligned)} passages")

    # Save aligned data
    print(f"\nTotal aligned passages: {len(all_aligned)} / {len(en_passages)}")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_aligned, f, ensure_ascii=False, indent=None)

    print(f"Saved to: {OUTPUT_PATH}")

    # Quality stats
    if all_aligned:
        lengths = [len(v) for v in all_aligned.values()]
        avg_len = sum(lengths) / len(lengths)
        print(f"\nAlignment quality stats:")
        print(f"  Average French passage length: {avg_len:.0f} chars")
        print(f"  Min: {min(lengths)}, Max: {max(lengths)}")
        print(f"  Coverage: {len(all_aligned) / len(en_passages) * 100:.1f}%")


if __name__ == "__main__":
    main()
