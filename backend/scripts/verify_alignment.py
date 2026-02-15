#!/usr/bin/env python3
"""
Verify alignment quality of bilingual Proust passages.

Checks:
1. FR/EN character ratio per passage (expect 0.8-1.5)
2. Sample passages for manual side-by-side inspection
3. First sentences of each chapter match known openings
4. Empty/missing French text detection

Usage:
    cd backend
    python scripts/verify_alignment.py
    python scripts/verify_alignment.py --samples 30   # more sample passages
"""

import argparse
import json
import random
import sys
from pathlib import Path
from collections import Counter

BACKEND_DIR = Path(__file__).parent.parent
DATA_PATH = BACKEND_DIR / "parsed_clean_bilingual.json"

# Known opening lines for spot-checking alignment
KNOWN_OPENINGS = {
    (1, "Overture"): {
        "en": "For a long time I used to go to bed early",
        "fr": "Longtemps, je me suis couch",
    },
    (1, "Swann in Love"): {
        "en": "To admit you to the",
        "fr": "Pour faire partie",
    },
    (1, "Place-Names: The Name"): {
        "en": "Among the rooms",
        "fr": "Parmi les chambres",
    },
    (2, "Madame Swann at Home"): {
        "en": "",  # Will check whatever it starts with
        "fr": "",
    },
    (7, "Chapter 1 \u2014 Tansonville"): {
        "en": "",
        "fr": "",
    },
}


def load_passages() -> list[dict]:
    """Load the bilingual passages."""
    if not DATA_PATH.exists():
        print(f"ERROR: {DATA_PATH} not found")
        print("Run align_sentences.py first.")
        sys.exit(1)

    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def check_char_ratios(passages: list[dict]) -> dict:
    """Compute FR/EN character ratio per passage.

    Expected range: 0.8-1.5 (French tends to be slightly longer than English).
    """
    ratios = []
    outliers = []

    for p in passages:
        en_len = len(p.get("text", ""))
        fr_len = len(p.get("text_fr", ""))

        if en_len == 0 or fr_len == 0:
            continue

        ratio = fr_len / en_len
        ratios.append(ratio)

        if ratio < 0.5 or ratio > 2.5:
            outliers.append({
                "index": p.get("index"),
                "volume": p.get("volume"),
                "chapter": p.get("chapter"),
                "en_len": en_len,
                "fr_len": fr_len,
                "ratio": round(ratio, 2),
            })

    if not ratios:
        return {"avg": 0, "min": 0, "max": 0, "outliers": 0}

    return {
        "avg": round(sum(ratios) / len(ratios), 3),
        "min": round(min(ratios), 3),
        "max": round(max(ratios), 3),
        "median": round(sorted(ratios)[len(ratios) // 2], 3),
        "in_range": sum(1 for r in ratios if 0.8 <= r <= 1.5),
        "total": len(ratios),
        "pct_in_range": round(sum(1 for r in ratios if 0.8 <= r <= 1.5) / len(ratios) * 100, 1),
        "outliers": len(outliers),
        "outlier_samples": outliers[:5],
    }


def check_coverage(passages: list[dict]) -> dict:
    """Check how many passages have French text."""
    total = len(passages)
    has_fr = sum(1 for p in passages if p.get("text_fr"))
    empty_fr = sum(1 for p in passages if not p.get("text_fr"))

    per_volume = Counter()
    fr_per_volume = Counter()
    for p in passages:
        vol = p.get("volume", 0)
        per_volume[vol] += 1
        if p.get("text_fr"):
            fr_per_volume[vol] += 1

    return {
        "total": total,
        "has_fr": has_fr,
        "empty_fr": empty_fr,
        "coverage_pct": round(has_fr / total * 100, 1) if total else 0,
        "per_volume": {
            vol: {
                "total": per_volume[vol],
                "has_fr": fr_per_volume.get(vol, 0),
                "pct": round(fr_per_volume.get(vol, 0) / per_volume[vol] * 100, 1),
            }
            for vol in sorted(per_volume)
        },
    }


def check_openings(passages: list[dict]) -> list[dict]:
    """Verify known opening sentences match."""
    results = []

    # Build lookup: (volume, chapter) -> first passage
    first_passages = {}
    for p in passages:
        key = (p.get("volume"), p.get("chapter"))
        if key not in first_passages:
            first_passages[key] = p

    for key, expected in KNOWN_OPENINGS.items():
        p = first_passages.get(key)
        result = {"volume": key[0], "chapter": key[1]}

        if not p:
            result["status"] = "MISSING"
            results.append(result)
            continue

        en_text = p.get("text", "")[:100]
        fr_text = p.get("text_fr", "")[:100]

        en_ok = not expected["en"] or expected["en"].lower() in en_text.lower()
        fr_ok = not expected["fr"] or expected["fr"].lower() in fr_text.lower()

        result["en_start"] = en_text[:60]
        result["fr_start"] = fr_text[:60]
        result["en_ok"] = en_ok
        result["fr_ok"] = fr_ok
        result["status"] = "OK" if (en_ok and fr_ok) else "MISMATCH"
        results.append(result)

    return results


def check_fr_uniqueness(passages: list[dict]) -> dict:
    """Count consecutive duplicate French texts within same chapter.

    After FR-primary alignment, there should be 0 consecutive duplicates.
    """
    consecutive_dupes = 0
    per_chapter: dict[str, int] = {}

    for i in range(1, len(passages)):
        curr_fr = passages[i].get("text_fr", "")
        prev_fr = passages[i - 1].get("text_fr", "")

        same_chapter = (
            passages[i].get("volume") == passages[i - 1].get("volume")
            and passages[i].get("chapter") == passages[i - 1].get("chapter")
        )

        if same_chapter and curr_fr and curr_fr == prev_fr:
            consecutive_dupes += 1
            key = f"Vol {passages[i].get('volume')}, {passages[i].get('chapter')}"
            per_chapter[key] = per_chapter.get(key, 0) + 1

    return {
        "consecutive_duplicates": consecutive_dupes,
        "per_chapter": per_chapter,
    }


def check_length_ratio_distribution(passages: list[dict]) -> dict:
    """Analyze the distribution of EN/FR length ratios in buckets."""
    buckets = {
        "0.0-0.5": 0,
        "0.5-0.8": 0,
        "0.8-1.0": 0,
        "1.0-1.2": 0,
        "1.2-1.5": 0,
        "1.5-2.0": 0,
        "2.0-3.0": 0,
        "3.0+": 0,
    }
    total = 0
    over_3x = 0

    for p in passages:
        en_len = len(p.get("text", ""))
        fr_len = len(p.get("text_fr", ""))
        if en_len == 0 or fr_len == 0:
            continue

        total += 1
        ratio = fr_len / en_len

        if ratio < 0.5:
            buckets["0.0-0.5"] += 1
        elif ratio < 0.8:
            buckets["0.5-0.8"] += 1
        elif ratio < 1.0:
            buckets["0.8-1.0"] += 1
        elif ratio < 1.2:
            buckets["1.0-1.2"] += 1
        elif ratio < 1.5:
            buckets["1.2-1.5"] += 1
        elif ratio < 2.0:
            buckets["1.5-2.0"] += 1
        elif ratio < 3.0:
            buckets["2.0-3.0"] += 1
        else:
            buckets["3.0+"] += 1

        # Also check the inverse direction
        max_ratio = max(en_len, fr_len) / min(en_len, fr_len)
        if max_ratio > 3.0:
            over_3x += 1

    return {
        "total": total,
        "buckets": buckets,
        "over_3x": over_3x,
        "over_3x_pct": round(over_3x / total * 100, 1) if total else 0,
    }


def check_per_chapter_stats(passages: list[dict]) -> list[dict]:
    """Compute per-chapter alignment quality statistics."""
    from collections import defaultdict

    chapters = defaultdict(list)
    for p in passages:
        key = (p.get("volume"), p.get("chapter"))
        chapters[key].append(p)

    stats = []
    for (vol, ch), chapter_passages in sorted(chapters.items()):
        total = len(chapter_passages)
        has_fr = sum(1 for p in chapter_passages if p.get("text_fr"))
        fr_pct = has_fr / total * 100 if total else 0

        # Compute ratio stats for this chapter
        ratios_ok = 0
        ratios_total = 0
        for p in chapter_passages:
            en_len = len(p.get("text", ""))
            fr_len = len(p.get("text_fr", ""))
            if en_len > 0 and fr_len > 0:
                ratios_total += 1
                ratio = fr_len / en_len
                if 0.5 <= ratio <= 2.0:
                    ratios_ok += 1

        ratio_pct_ok = ratios_ok / ratios_total * 100 if ratios_total else 0

        stats.append({
            "volume": vol,
            "chapter": ch,
            "count": total,
            "has_fr": has_fr,
            "fr_pct": round(fr_pct, 1),
            "ratio_pct_ok": round(ratio_pct_ok, 1),
        })

    return stats


def sample_passages(passages: list[dict], n: int = 20) -> list[dict]:
    """Sample N passages for side-by-side manual inspection."""
    # Sample evenly across volumes
    by_volume: dict[int, list[dict]] = {}
    for p in passages:
        if p.get("text_fr"):
            vol = p.get("volume", 0)
            if vol not in by_volume:
                by_volume[vol] = []
            by_volume[vol].append(p)

    samples = []
    per_vol = max(1, n // len(by_volume)) if by_volume else 0

    for vol in sorted(by_volume):
        vol_passages = by_volume[vol]
        k = min(per_vol, len(vol_passages))
        samples.extend(random.sample(vol_passages, k))

    # Fill remaining slots randomly
    all_fr = [p for p in passages if p.get("text_fr")]
    while len(samples) < n and all_fr:
        p = random.choice(all_fr)
        if p not in samples:
            samples.append(p)

    return samples[:n]


def main():
    parser = argparse.ArgumentParser(description="Verify bilingual alignment quality")
    parser.add_argument("--samples", type=int, default=20,
                        help="Number of sample passages to display")
    args = parser.parse_args()

    print("Bilingual Alignment Verification")
    print("=" * 60)

    passages = load_passages()
    print(f"Loaded {len(passages)} passages from {DATA_PATH.name}")

    # 1. Coverage
    print(f"\n--- Coverage ---")
    coverage = check_coverage(passages)
    print(f"  Total passages:  {coverage['total']}")
    print(f"  With French:     {coverage['has_fr']} ({coverage['coverage_pct']}%)")
    print(f"  Missing French:  {coverage['empty_fr']}")
    print(f"\n  Per-volume:")
    for vol, stats in coverage["per_volume"].items():
        print(f"    Vol {vol}: {stats['has_fr']}/{stats['total']} ({stats['pct']}%)")

    # 2. FR uniqueness
    print(f"\n--- FR Uniqueness ---")
    uniqueness = check_fr_uniqueness(passages)
    dupes = uniqueness["consecutive_duplicates"]
    print(f"  Consecutive FR duplicates: {dupes}")
    if dupes > 0:
        print(f"  Per chapter:")
        for ch, count in sorted(uniqueness["per_chapter"].items()):
            print(f"    {ch}: {count}")
    else:
        print(f"  PASS: No repeated French text!")

    # 3. Character ratios
    print(f"\n--- FR/EN Character Ratios ---")
    ratios = check_char_ratios(passages)
    print(f"  Average: {ratios['avg']}")
    print(f"  Median:  {ratios.get('median', 'N/A')}")
    print(f"  Range:   {ratios['min']} - {ratios['max']}")
    print(f"  In [0.8, 1.5]: {ratios.get('in_range', 0)}/{ratios.get('total', 0)} "
          f"({ratios.get('pct_in_range', 0)}%)")
    if ratios.get("outlier_samples"):
        print(f"  Outliers (ratio < 0.5 or > 2.5): {ratios['outliers']}")
        for o in ratios["outlier_samples"]:
            print(f"    idx={o['index']} vol={o['volume']} ratio={o['ratio']} "
                  f"(EN:{o['en_len']}, FR:{o['fr_len']})")

    # 4. Opening line checks
    print(f"\n--- Opening Line Checks ---")
    openings = check_openings(passages)
    for r in openings:
        status = r["status"]
        icon = "OK" if status == "OK" else "!!"
        print(f"  [{icon}] Vol {r['volume']}, {r['chapter']}: {status}")
        if status != "MISSING":
            print(f"       EN: {r.get('en_start', '')}")
            print(f"       FR: {r.get('fr_start', '')}")

    # 5. Length ratio distribution
    print(f"\n--- Length Ratio Distribution ---")
    ratio_dist = check_length_ratio_distribution(passages)
    print(f"  Passages with both EN+FR: {ratio_dist['total']}")
    for bucket, count in sorted(ratio_dist["buckets"].items()):
        pct = count / ratio_dist["total"] * 100 if ratio_dist["total"] else 0
        bar = "#" * int(pct / 2)
        print(f"    {bucket:>10s}: {count:5d} ({pct:5.1f}%) {bar}")
    print(f"  >3x ratio (misaligned): {ratio_dist['over_3x']} "
          f"({ratio_dist['over_3x_pct']:.1f}%)")

    # 6. Per-chapter stats
    print(f"\n--- Per-Chapter Statistics ---")
    ch_stats = check_per_chapter_stats(passages)
    for s in ch_stats:
        quality = "OK" if s["ratio_pct_ok"] > 70 else "REVIEW" if s["ratio_pct_ok"] > 40 else "POOR"
        print(f"  Vol {s['volume']}, {s['chapter'][:40]:40s} "
              f"n={s['count']:4d} fr={s['fr_pct']:5.1f}% "
              f"ratio_ok={s['ratio_pct_ok']:5.1f}% [{quality}]")

    # 7. Sample passages
    print(f"\n--- Sample Passages (n={args.samples}) ---")
    samples = sample_passages(passages, args.samples)
    for i, p in enumerate(samples, 1):
        en_text = p.get("text", "")[:120]
        fr_text = p.get("text_fr", "")[:120]
        ratio = len(p.get("text_fr", "")) / max(len(p.get("text", "")), 1)
        print(f"\n  [{i}] Vol {p.get('volume')}, {p.get('chapter')}, "
              f"idx={p.get('index')} (ratio={ratio:.2f})")
        print(f"    EN: {en_text}...")
        print(f"    FR: {fr_text}...")

    # Summary
    print(f"\n{'='*60}")
    all_ok = (
        coverage["coverage_pct"] > 90
        and dupes == 0
        and ratios.get("pct_in_range", 0) > 60
        and ratio_dist.get("over_3x_pct", 100) < 5
        and all(r["status"] == "OK" for r in openings if r["status"] != "MISSING")
    )
    if all_ok:
        print("PASS: Alignment looks good!")
    else:
        print("REVIEW: Some alignment issues detected. Check details above.")


if __name__ == "__main__":
    main()
