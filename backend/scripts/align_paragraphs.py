"""
Paragraph-level bilingual alignment of English and French Proust texts.

Replaces the character-level proportional alignment in align_french_text.py
with paragraph-level alignment for much better semantic boundaries.

For each volume/chapter pair:
1. Split both EN and FR chapter texts into paragraphs (double-newline boundaries)
2. Align paragraphs proportionally: paragraph i in EN maps to paragraph
   round(i * M / N) in FR, where N = EN paragraph count, M = FR paragraph count
3. Output aligned paragraph pairs

Usage:
    cd backend
    python scripts/align_paragraphs.py
"""

import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
EN_DIR = DATA_DIR / "english_raw"
FR_DIR = DATA_DIR / "french_raw"
OUTPUT_PATH = DATA_DIR / "aligned_paragraphs.json"

# ── Chapter name mapping ──────────────────────────────────────────────────
# Maps (volume, EN chapter name) to the index of the French chapter within
# that volume's chapter list. This accounts for structural differences
# between the EN corpus (which merges some SE chapters) and the FR
# Wikisource chapters.
#
# French volumes have these chapter structures:
#   Vol 1: Partie 1, Partie 2, Partie 3
#   Vol 2: Première partie, Deuxième partie, Troisième partie
#   Vol 3: Première partie, Deuxième partie, Troisième partie
#   Vol 4: Partie 1, Partie 2 - chapitre 1, ..., Partie 2 - chapitre 4
#   Vol 5: Chapitre 1, Chapitre 2, Chapitre 3
#   Vol 6: Chapitre I, Chapitre II, Chapitre III, Chapitre IV
#   Vol 7: I, II, III

EN_TO_FR_CHAPTER_MAP = {
    # Vol 1: EN has 3 chapters, FR has 3 parts
    (1, "Overture"): [0],               # FR Partie 1
    (1, "Swann in Love"): [1],           # FR Partie 2
    (1, "Place-Names: The Name"): [2],   # FR Partie 3

    # Vol 2: EN has 3 chapters, FR has 3 parts
    (2, "Madame Swann at Home"): [0],                    # FR Première partie
    (2, "Place-Names: The Place"): [1],                  # FR Deuxième partie
    (2, "Seascape, with Frieze of Girls"): [2],          # FR Troisième partie

    # Vol 3: EN has 3 parts matching FR's 3 parts (1:1)
    (3, "Part 1"): [0],               # FR Première partie
    (3, "Part 2"): [1],               # FR Deuxième partie
    (3, "Part 3"): [2],               # FR Troisième partie

    # Vol 4: EN has 5 chapters, FR has 5 sections
    (4, "Introduction"): [0],                    # FR Partie 1
    (4, "Chapter 1"): [1],                       # FR Partie 2 - chapitre 1
    (4, "Chapter 2"): [2],                       # FR Partie 2 - chapitre 2
    (4, "Chapter 3"): [3],                       # FR Partie 2 - chapitre 3
    (4, "Chapter 4"): [4],                       # FR Partie 2 - chapitre 4

    # Vol 5: EN has 3 chapters, FR has 3 chapters (1:1)
    (5, "Chapter 1 \u2014 Life with Albertine"): [0],
    (5, "Chapter 2 \u2014 The Verdurins Quarrel with M. De Charlus"): [1],
    (5, "Chapter 3 \u2014 Flight of Albertine"): [2],

    # Vol 6: EN has 4 chapters, FR has 4 chapters (1:1)
    (6, "Chapter 1 \u2014 Grief and Oblivion"): [0],
    (6, "Chapter 2 \u2014 Mademoiselle De Forcheville"): [1],
    (6, "Chapter 3 \u2014 Venice"): [2],
    (6, "Chapter 4 \u2014 A Fresh Light Upon Robert De Saint-Loup"): [3],

    # Vol 7: EN has 3 chapters, FR has 3 chapters (1:1)
    (7, "Chapter 1 \u2014 Tansonville"): [0],
    (7, "Chapter 2 \u2014 M. de Charlus During the War, His Opinions, His Pleasures"): [1],
    (7, "Chapter 3 \u2014 An Afternoon Party at the House of the Princesse de Guermantes"): [2],
}


def split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs on double-newline boundaries.

    Returns non-empty paragraphs with internal whitespace normalized.
    """
    # Split on 2+ consecutive newlines
    raw = re.split(r"\n\s*\n", text)
    paragraphs = []
    for p in raw:
        cleaned = p.strip()
        # Normalize internal whitespace (collapse multiple spaces)
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        if cleaned:
            paragraphs.append(cleaned)
    return paragraphs


def align_paragraphs_fr_primary(
    en_paragraphs: list[str],
    fr_paragraphs: list[str],
) -> list[tuple[str, str]]:
    """FR-primary proportional alignment: partition the majority side into
    groups mapped 1:1 to the minority side. Guarantees no repeated text.

    Output count = min(len(en), len(fr)). The majority side's paragraphs
    are grouped into contiguous chunks using proportional partitioning
    (round(i * N / M) boundaries). Grouped paragraphs are concatenated
    with a space separator.

    Returns list of (en_text, fr_text) pairs.
    """
    if not en_paragraphs or not fr_paragraphs:
        return [(p, "") for p in en_paragraphs]

    N_en = len(en_paragraphs)
    N_fr = len(fr_paragraphs)

    if N_en >= N_fr:
        # EN is majority: partition N_en into N_fr groups
        src = en_paragraphs
        tgt = fr_paragraphs
        src_count, tgt_count = N_en, N_fr
        en_majority = True
    else:
        # FR is majority: partition N_fr into N_en groups
        src = fr_paragraphs
        tgt = en_paragraphs
        src_count, tgt_count = N_fr, N_en
        en_majority = False

    pairs = []
    for k in range(tgt_count):
        start = round(k * src_count / tgt_count)
        end = round((k + 1) * src_count / tgt_count)
        grouped = "\n\n".join(src[start:end])

        if en_majority:
            pairs.append((grouped, tgt[k]))
        else:
            pairs.append((tgt[k], grouped))

    return pairs


def load_english_volumes() -> dict[int, dict]:
    """Load all downloaded English volumes."""
    english = {}
    for vol_file in sorted(EN_DIR.glob("volume_*.json")):
        with open(vol_file, encoding="utf-8") as f:
            data = json.load(f)
            english[data["volume"]] = data
    return english


def load_french_volumes() -> dict[int, dict]:
    """Load all downloaded French volumes."""
    french = {}
    for vol_file in sorted(FR_DIR.glob("volume_*.json")):
        with open(vol_file, encoding="utf-8") as f:
            data = json.load(f)
            french[data["volume"]] = data
    return french


def align_chapter(
    en_text: str,
    fr_text: str,
    volume: int,
    chapter: str,
    book: str,
) -> list[dict]:
    """Align a single chapter's paragraphs between EN and FR.

    Returns list of aligned paragraph records.
    """
    en_paragraphs = split_paragraphs(en_text)
    fr_paragraphs = split_paragraphs(fr_text)

    # Report alignment quality
    ratio = len(fr_paragraphs) / len(en_paragraphs) if en_paragraphs else 0
    diff_pct = abs(len(en_paragraphs) - len(fr_paragraphs)) / max(len(en_paragraphs), 1) * 100

    if diff_pct > 30:
        print(f"    WARNING: paragraph count differs by {diff_pct:.0f}% "
              f"(EN: {len(en_paragraphs)}, FR: {len(fr_paragraphs)})")

    pairs = align_paragraphs_fr_primary(en_paragraphs, fr_paragraphs)

    records = []
    for en_p, fr_p in pairs:
        records.append({
            "text": en_p,
            "text_fr": fr_p,
            "volume": volume,
            "chapter": chapter,
            "book": book,
        })

    return records


def main():
    print("Paragraph-level bilingual alignment")
    print("=" * 60)

    # Load both corpora
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

    # Align each chapter
    all_records: list[dict] = []
    total_warnings = 0

    for vol_num in sorted(set(en_volumes.keys()) & set(fr_volumes.keys())):
        en_vol = en_volumes[vol_num]
        fr_vol = fr_volumes[vol_num]
        print(f"\nVolume {vol_num}: {en_vol.get('book', '?')}")

        en_chapters = en_vol.get("chapters", [])
        fr_chapters = fr_vol.get("chapters", [])

        for en_ch in en_chapters:
            ch_name = en_ch["chapter"]
            key = (vol_num, ch_name)

            # Look up which FR chapter(s) to use
            fr_indices = EN_TO_FR_CHAPTER_MAP.get(key)
            if fr_indices is None:
                print(f"  WARNING: No FR mapping for {key}, skipping")
                total_warnings += 1
                # Still include EN text with empty FR
                for p in split_paragraphs(en_ch["text"]):
                    all_records.append({
                        "text": p,
                        "text_fr": "",
                        "volume": vol_num,
                        "chapter": ch_name,
                        "book": en_vol.get("book", "Unknown"),
                    })
                continue

            # Get FR text (merge multiple FR chapters if needed)
            fr_texts = []
            for idx in fr_indices:
                if idx < len(fr_chapters):
                    fr_texts.append(fr_chapters[idx].get("text", ""))
                else:
                    print(f"  WARNING: FR chapter index {idx} out of range for vol {vol_num}")
                    total_warnings += 1

            fr_combined = "\n\n".join(fr_texts)

            print(f"  {ch_name}:")
            print(f"    EN: {len(en_ch['text']):,} chars")
            print(f"    FR: {len(fr_combined):,} chars")

            records = align_chapter(
                en_ch["text"],
                fr_combined,
                vol_num,
                ch_name,
                en_vol.get("book", "Unknown"),
            )
            all_records.extend(records)
            print(f"    Aligned: {len(records)} paragraph pairs")

    # Save output
    print(f"\n{'='*60}")
    print(f"Total aligned paragraph pairs: {len(all_records)}")
    if total_warnings:
        print(f"Warnings: {total_warnings}")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)

    print(f"Saved to: {OUTPUT_PATH}")

    # Quality stats
    en_lens = [len(r["text"]) for r in all_records]
    fr_lens = [len(r["text_fr"]) for r in all_records if r["text_fr"]]
    print(f"\nEN paragraph stats: avg={sum(en_lens)/len(en_lens):.0f}, "
          f"min={min(en_lens)}, max={max(en_lens)}")
    if fr_lens:
        print(f"FR paragraph stats: avg={sum(fr_lens)/len(fr_lens):.0f}, "
              f"min={min(fr_lens)}, max={max(fr_lens)}")

    # Check first paragraph
    if all_records:
        first = all_records[0]
        print(f"\nFirst EN paragraph starts: {first['text'][:80]}...")
        print(f"First FR paragraph starts: {first['text_fr'][:80]}...")


if __name__ == "__main__":
    main()
