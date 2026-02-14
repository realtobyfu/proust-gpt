"""
Merge aligned French text into the bilingual corpus.

Reads parsed_clean.json and french_aligned.json, adds a 'text_fr' field
to each passage, and saves as parsed_clean_bilingual.json.

Usage:
    cd backend
    python scripts/merge_french_text.py
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
PARSED_PATH = BASE_DIR / "parsed_clean.json"
ALIGNED_PATH = BASE_DIR / "data" / "french_aligned.json"
OUTPUT_PATH = BASE_DIR / "parsed_clean_bilingual.json"


def main():
    print("Merging French text into bilingual corpus...")

    # Load English corpus
    print("Loading parsed_clean.json...")
    with open(PARSED_PATH, encoding="utf-8") as f:
        passages = json.load(f)
    print(f"  {len(passages)} passages")

    # Load aligned French text
    print("Loading french_aligned.json...")
    if not ALIGNED_PATH.exists():
        print(f"  File not found: {ALIGNED_PATH}")
        print("  Run align_french_text.py first.")
        return

    with open(ALIGNED_PATH, encoding="utf-8") as f:
        # Keys are passage index strings (JSON keys are always strings)
        aligned_raw = json.load(f)

    # Convert string keys to int
    aligned: dict[int, str] = {int(k): v for k, v in aligned_raw.items()}
    print(f"  {len(aligned)} aligned French passages")

    # Merge
    matched = 0
    for p in passages:
        idx = p.get("index")
        if idx is not None and idx in aligned:
            p["text_fr"] = aligned[idx]
            matched += 1
        else:
            p["text_fr"] = None

    print(f"\nMerged: {matched} / {len(passages)} passages have French text")
    print(f"Coverage: {matched / len(passages) * 100:.1f}%")

    # Validate: check length ratios per volume
    print("\nPer-volume coverage:")
    volume_stats: dict[int, dict] = {}
    for p in passages:
        vol = p.get("volume", 1)
        if vol not in volume_stats:
            volume_stats[vol] = {"total": 0, "with_fr": 0, "ratios": []}
        volume_stats[vol]["total"] += 1
        if p.get("text_fr"):
            volume_stats[vol]["with_fr"] += 1
            en_len = len(p.get("text", ""))
            fr_len = len(p["text_fr"])
            if en_len > 0:
                volume_stats[vol]["ratios"].append(fr_len / en_len)

    for vol_num in sorted(volume_stats.keys()):
        stats = volume_stats[vol_num]
        coverage = stats["with_fr"] / stats["total"] * 100 if stats["total"] > 0 else 0
        avg_ratio = (
            sum(stats["ratios"]) / len(stats["ratios"])
            if stats["ratios"]
            else 0
        )
        print(
            f"  Vol {vol_num}: {stats['with_fr']}/{stats['total']} "
            f"({coverage:.0f}%) | avg FR/EN ratio: {avg_ratio:.2f}"
        )

    # Save
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(passages, f, ensure_ascii=False, indent=None)

    print(f"\nSaved bilingual corpus to: {OUTPUT_PATH}")
    print(f"File size: {OUTPUT_PATH.stat().st_size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
