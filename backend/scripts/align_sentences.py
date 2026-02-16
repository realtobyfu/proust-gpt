#!/usr/bin/env python3
"""
Bilingual alignment using proper-noun anchoring + proportional paragraph mapping.

Replaces the Cohere-dependent sentence-level DP alignment with a local approach
that cannot cascade drift:

1. Split chapters into paragraphs (double-newline boundaries)
2. Extract proper-noun anchors (character names identical in EN and FR)
3. LCS-match anchor sequences to find reliable correspondence points
4. Between each pair of anchors, align paragraphs by proportional character position
5. Chunk aligned paragraph pairs into 500-1500 char passages

No API calls needed.  Alignment resets at every anchor (~every 2000-5000 chars),
preventing the cascading drift that affected the DP approach.

Usage:
    cd backend
    python scripts/align_sentences.py             # Full corpus
    python scripts/align_sentences.py --test       # Vol 1 Overture only
    python scripts/align_sentences.py --volume 3   # Single volume
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).parent.parent / "data"
EN_DIR = DATA_DIR / "english_raw"
FR_DIR = DATA_DIR / "french_raw"
ALIGNED_SENTS_PATH = DATA_DIR / "aligned_sentences.json"
OUTPUT_PATH = Path(__file__).parent.parent / "parsed_clean_bilingual.json"

# ── Chunk size targets ───────────────────────────────────────────────────────

MIN_CHUNK_CHARS = 250
MAX_CHUNK_CHARS = 750
SHORT_THRESHOLD = 80  # merge chunks shorter than this


# ── Chapter mapping ──────────────────────────────────────────────────────────

EN_TO_FR_CHAPTER_MAP = {
    # Vol 1: EN has 3 chapters, FR has 3 parts
    (1, "Overture"): [0],
    (1, "Swann in Love"): [1],
    (1, "Place-Names: The Name"): [2],

    # Vol 2: EN has 3 chapters, FR has 3 parts
    (2, "Madame Swann at Home"): [0],
    (2, "Place-Names: The Place"): [1],
    (2, "Seascape, with Frieze of Girls"): [2],

    # Vol 3: aligned as whole volume, split by FR chapter boundaries (see below)

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

# Volumes where EN/FR chapter boundaries differ, so all chapters are
# concatenated and aligned as one unit.  Output passages are then split
# into the correct FR chapter names based on FR character positions.
WHOLE_VOLUME_ALIGN = {3}

# FR chapter names for Vol 3 (French is the original, so its structure is
# authoritative).  The alignment output will be split using these names.
VOL3_FR_CHAPTER_NAMES = [
    "Première partie",
    "Deuxième partie",
    "Troisième partie",
]


# ── Proper noun anchors ─────────────────────────────────────────────────────

# Character and place names identical in EN and FR.
# These appear every ~400-600 characters in Proust's text.
ANCHOR_NAMES = [
    "Swann", "Guermantes", "Françoise", "Charlus", "Albertine", "Saint-Loup",
    "Odette", "Gilberte", "Cottard", "Verdurin", "Vinteuil", "Norpois",
    "Elstir", "Bergotte", "Bloch", "Jupien", "Morel", "Villeparisis",
    "Brichot", "Saniette", "Oriane", "Legrandin", "Combray", "Balbec",
    "Méséglise", "Tansonville", "Léonie", "Eulalie", "Forcheville",
    "Cambremer", "Madeleine", "Montjouvain", "Robert", "Rachel",
    "Andrée", "Bontemps",
]

# Pre-compile regex for anchor extraction: match whole words only
_ANCHOR_RE = re.compile(
    r"\b(" + "|".join(re.escape(n) for n in ANCHOR_NAMES) + r")\b"
)


def extract_anchors(text: str) -> list[tuple[int, str]]:
    """Find all proper-noun anchor occurrences with character positions.

    Returns list of (char_position, name) sorted by position.
    """
    return [(m.start(), m.group(1)) for m in _ANCHOR_RE.finditer(text)]


def lcs_anchor_pairs(
    en_anchors: list[tuple[int, str]],
    fr_anchors: list[tuple[int, str]],
    en_total_len: int,
    fr_total_len: int,
    band_pct: float = 0.15,
) -> list[tuple[int, int]]:
    """LCS of name sequences -> list of (en_char_pos, fr_char_pos) anchor pairs.

    Uses a band constraint: only match names within ±band_pct of expected
    diagonal position, to prevent matching a "Swann" at the start of EN
    with a "Swann" at the end of FR.

    Args:
        en_anchors: [(char_pos, name), ...] from EN text
        fr_anchors: [(char_pos, name), ...] from FR text
        en_total_len: total length of EN text
        fr_total_len: total length of FR text
        band_pct: maximum proportional distance from diagonal (0.15 = ±15%)

    Returns:
        List of (en_char_pos, fr_char_pos) pairs, sorted by position.
    """
    if not en_anchors or not fr_anchors or en_total_len == 0 or fr_total_len == 0:
        return []

    n = len(en_anchors)
    m = len(fr_anchors)

    # Precompute normalized positions
    en_norm = [pos / en_total_len for pos, _ in en_anchors]
    fr_norm = [pos / fr_total_len for pos, _ in fr_anchors]

    # Standard LCS DP with band constraint
    dp = [[0] * (m + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if (en_anchors[i - 1][1] == fr_anchors[j - 1][1]
                    and abs(en_norm[i - 1] - fr_norm[j - 1]) <= band_pct):
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

    # Backtrack
    pairs = []
    i, j = n, m
    while i > 0 and j > 0:
        if (en_anchors[i - 1][1] == fr_anchors[j - 1][1]
                and abs(en_norm[i - 1] - fr_norm[j - 1]) <= band_pct
                and dp[i][j] == dp[i - 1][j - 1] + 1):
            pairs.append((en_anchors[i - 1][0], fr_anchors[j - 1][0]))
            i -= 1
            j -= 1
        elif dp[i - 1][j] >= dp[i][j - 1]:
            i -= 1
        else:
            j -= 1

    pairs.reverse()
    return pairs


def sparsify_anchors(
    pairs: list[tuple[int, int]], min_spacing: int = 2000,
) -> list[tuple[int, int]]:
    """Keep only anchors >= min_spacing chars apart to avoid over-fragmentation.

    Greedily selects pairs that are at least min_spacing apart in both
    EN and FR character positions.
    """
    if not pairs:
        return []

    result = [pairs[0]]
    for en_pos, fr_pos in pairs[1:]:
        last_en, last_fr = result[-1]
        if en_pos - last_en >= min_spacing and fr_pos - last_fr >= min_spacing:
            result.append((en_pos, fr_pos))

    return result


# ── Text splitting ───────────────────────────────────────────────────────────

def split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs on double-newline boundaries.

    Also merges orphaned French guillemets (»  or «) back into adjacent
    paragraphs, fixing an NLTK tokenization artifact.
    """
    raw = re.split(r"\n\s*\n", text)
    paragraphs = []
    for p in raw:
        cleaned = p.strip()
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        if not cleaned:
            continue
        # Merge orphaned guillemets into previous paragraph
        if len(cleaned) < 5 and re.match(r'^[»«\s]+$', cleaned):
            if paragraphs:
                paragraphs[-1] = paragraphs[-1] + " " + cleaned
            continue
        paragraphs.append(cleaned)
    return paragraphs


# Section markers / artifacts to remove
_SECTION_MARKER_RE = re.compile(
    r"^[IVX]+\.?$"                       # Roman numerals
    r"|^[IVX]+\s*$"
    r"|^\*\s*\*\s*\*$"                   # Asterisk separators
    r"|^[-—–\*]{3,}$"                    # Dash/asterisk separators
    r"|^COMBRAY\s+[IVX]+$"              # COMBRAY I, COMBRAY II
    r"|^CHAPITRE\b"                      # French chapter headers
    r"|^CHAPTER\b",                      # English chapter headers
    re.IGNORECASE,
)


def _is_section_marker(text: str) -> bool:
    """Check if text is a section marker rather than narrative."""
    return bool(_SECTION_MARKER_RE.match(text.strip()))


def _filter_paragraphs(paragraphs: list[str]) -> list[str]:
    """Remove section markers from paragraph list."""
    return [p for p in paragraphs if not _is_section_marker(p)]


# ── FR-primary paragraph alignment ───────────────────────────────────────────

def _midpoints(paras: list[str]) -> list[float]:
    """Compute normalized cumulative midpoint positions for paragraphs."""
    lens = [len(p) for p in paras]
    total = sum(lens)
    if total == 0:
        return [i / len(paras) for i in range(len(paras))]
    cumul = 0
    mids = []
    for length in lens:
        mids.append((cumul + length / 2) / total)
        cumul += length
    return mids


def align_paragraphs_proportional(
    en_paras: list[str], fr_paras: list[str],
) -> list[tuple[str, str]]:
    """Align EN and FR paragraphs, preserving FR paragraph structure.

    French is the original text, so each FR paragraph is kept intact.
    EN paragraphs are grouped/mapped to their nearest FR paragraph by
    proportional character position.

    Returns list of (en_text, fr_text) aligned pairs — one per FR paragraph.
    """
    if not en_paras and not fr_paras:
        return []
    if not fr_paras:
        # No FR — return EN paragraphs with empty FR
        return [(" ".join(en_paras), "")]
    if not en_paras:
        # No EN — return FR paragraphs with empty EN
        return [("", p) for p in fr_paras]

    en_mids = _midpoints(en_paras)
    fr_mids = _midpoints(fr_paras)

    n_fr = len(fr_paras)

    # For each EN paragraph, find nearest FR paragraph
    assignments = []
    for mid in en_mids:
        best_idx = 0
        best_dist = abs(mid - fr_mids[0])
        for k in range(1, n_fr):
            d = abs(mid - fr_mids[k])
            if d < best_dist:
                best_dist = d
                best_idx = k
        assignments.append(best_idx)

    # Group consecutive EN paragraphs assigned to the same FR paragraph
    # Result: one entry per FR paragraph
    en_groups: dict[int, list[str]] = {}
    i = 0
    while i < len(en_paras):
        target = assignments[i]
        if target not in en_groups:
            en_groups[target] = []
        en_groups[target].append(en_paras[i])
        i += 1

    # Build output: one pair per FR paragraph (preserving FR order)
    pairs = []
    for fr_idx in range(n_fr):
        en_text = " ".join(en_groups.get(fr_idx, []))
        pairs.append((en_text, fr_paras[fr_idx]))

    return pairs


# ── Anchor-based alignment ───────────────────────────────────────────────────

def align_between_anchors(
    en_text: str, fr_text: str,
) -> list[tuple[str, str]]:
    """Align a window of text between two anchors.

    Splits into paragraphs, subdivides long paragraphs, and aligns
    proportionally.
    """
    en_paras = _filter_paragraphs(split_paragraphs(en_text))
    fr_paras = _filter_paragraphs(split_paragraphs(fr_text))

    if not en_paras and not fr_paras:
        return []
    if not en_paras:
        return [("", " ".join(fr_paras))]
    if not fr_paras:
        return [(" ".join(en_paras), "")]

    return align_paragraphs_proportional(en_paras, fr_paras)


def align_chapter(en_text: str, fr_text: str) -> list[tuple[str, str]]:
    """Full anchor-based alignment pipeline for a chapter.

    1. Extract proper-noun anchors from both texts
    2. LCS-match anchor sequences
    3. Sparsify to prevent over-fragmentation
    4. Between each pair of anchors, align proportionally
    5. Return list of (en_text, fr_text) aligned paragraph pairs
    """
    en_anchors = extract_anchors(en_text)
    fr_anchors = extract_anchors(fr_text)

    anchor_pairs = lcs_anchor_pairs(
        en_anchors, fr_anchors, len(en_text), len(fr_text),
    )
    anchor_pairs = sparsify_anchors(anchor_pairs, min_spacing=2000)

    # Add sentinel anchors at start and end
    sentinels = [(0, 0)] + anchor_pairs + [(len(en_text), len(fr_text))]

    all_pairs: list[tuple[str, str]] = []

    for idx in range(len(sentinels) - 1):
        en_start, fr_start = sentinels[idx]
        en_end, fr_end = sentinels[idx + 1]

        en_window = en_text[en_start:en_end]
        fr_window = fr_text[fr_start:fr_end]

        if not en_window.strip() and not fr_window.strip():
            continue

        window_pairs = align_between_anchors(en_window, fr_window)
        all_pairs.extend(window_pairs)

    return all_pairs


# ── Chunking ─────────────────────────────────────────────────────────────────

# Multi-level sentence splitting for EN + FR (Proust writes 3000+ char sentences)
# L1: standard sentence boundaries
_SENT_L1 = re.compile(r'(?<=[.!?\u2026\u00BB])\s+(?=[A-ZÀ-Ö\u00AB"\u201C\u2014])')
# L2: also split on ; and : followed by uppercase/quote
_SENT_L2 = re.compile(r'(?<=[.!?\u2026\u00BB;:])\s+(?=[A-ZÀ-Ö\u00AB"\u201C\u2014])')
# L3: split on any sentence-ending punctuation + whitespace (last resort)
_SENT_L3 = re.compile(r'(?<=[.!?\u2026;,])\s+')


def _split_at_sentences(text: str) -> list[str]:
    """Split text into sentences, progressively more aggressive."""
    for regex in (_SENT_L1, _SENT_L2, _SENT_L3):
        parts = regex.split(text)
        if len(parts) > 1:
            return [p for p in parts if p.strip()]
    return [text.strip()] if text.strip() else []


def _subdivide_long_pairs(
    pairs: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Split paragraph pairs that exceed MAX_CHUNK_CHARS at sentence boundaries.

    Proust writes paragraphs of 2000-4000+ chars. To get smaller chunks,
    we split both EN and FR at sentence boundaries, then re-pair proportionally.
    """
    result: list[tuple[str, str]] = []

    for en_text, fr_text in pairs:
        # Only split if the longer text exceeds the max
        if max(len(en_text), len(fr_text)) <= MAX_CHUNK_CHARS:
            result.append((en_text, fr_text))
            continue

        en_sents = _split_at_sentences(en_text)
        fr_sents = _split_at_sentences(fr_text)

        # If we can't split either side, keep as-is
        if len(en_sents) <= 1 and len(fr_sents) <= 1:
            result.append((en_text, fr_text))
            continue

        # Group sentences into sub-chunks targeting MAX_CHUNK_CHARS
        # Use FR as the guide (it's the original text)
        if len(fr_sents) > 1:
            fr_sub_chunks: list[str] = []
            cur: list[str] = []
            cur_len = 0
            for s in fr_sents:
                if cur and cur_len + len(s) > MAX_CHUNK_CHARS:
                    fr_sub_chunks.append(" ".join(cur))
                    cur = []
                    cur_len = 0
                cur.append(s)
                cur_len += len(s) + 1
            if cur:
                fr_sub_chunks.append(" ".join(cur))
        else:
            fr_sub_chunks = [fr_text]

        n_sub = len(fr_sub_chunks)

        # Proportionally split EN into the same number of sub-chunks
        if len(en_sents) >= n_sub and n_sub > 1:
            # Distribute EN sentences across sub-chunks proportionally
            en_sub_chunks: list[str] = []
            per_chunk = len(en_sents) / n_sub
            for k in range(n_sub):
                start_idx = int(round(k * per_chunk))
                end_idx = int(round((k + 1) * per_chunk))
                en_sub_chunks.append(" ".join(en_sents[start_idx:end_idx]))
        else:
            en_sub_chunks = [en_text]
            # Pad to match FR sub-chunks
            while len(en_sub_chunks) < n_sub:
                en_sub_chunks.append("")

        for en_sub, fr_sub in zip(en_sub_chunks, fr_sub_chunks):
            result.append((en_sub, fr_sub))

    return result


def group_pairs_into_chunks(
    pairs: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Merge aligned paragraph pairs into chunks of MIN-MAX_CHUNK_CHARS.

    First subdivides long paragraphs at sentence boundaries, then merges
    small pairs together. Uses FR text length to decide chunk boundaries.
    """
    if not pairs:
        return []

    # Subdivide long paragraphs before merging
    pairs = _subdivide_long_pairs(pairs)

    chunks: list[tuple[str, str]] = []
    cur_en_parts: list[str] = []
    cur_fr_parts: list[str] = []
    cur_fr_len = 0

    for en_text, fr_text in pairs:
        en_text = en_text.strip()
        fr_text = fr_text.strip()
        if not en_text and not fr_text:
            continue

        would_exceed = cur_fr_len + len(fr_text) > MAX_CHUNK_CHARS

        if cur_fr_parts and would_exceed and cur_fr_len >= MIN_CHUNK_CHARS:
            # Flush current chunk
            chunks.append((" ".join(cur_en_parts), " ".join(cur_fr_parts)))
            cur_en_parts = []
            cur_fr_parts = []
            cur_fr_len = 0

        cur_en_parts.append(en_text)
        cur_fr_parts.append(fr_text)
        cur_fr_len += len(fr_text) + 1  # +1 for joining space

    # Don't forget last chunk
    if cur_en_parts:
        chunks.append((" ".join(cur_en_parts), " ".join(cur_fr_parts)))

    # Merge very short chunks, then balance ratio mismatches
    merged = _merge_short_chunks(chunks)
    return _balance_ratios(merged)


def _merge_short_chunks(
    chunks: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Merge chunks shorter than SHORT_THRESHOLD with neighbors."""
    if len(chunks) <= 1:
        return chunks

    result = [chunks[0]]
    for en_text, fr_text in chunks[1:]:
        prev_en, prev_fr = result[-1]
        if len(en_text) < SHORT_THRESHOLD:
            result[-1] = (prev_en + " " + en_text, prev_fr + " " + fr_text)
        elif len(prev_en) < SHORT_THRESHOLD:
            result[-1] = (prev_en + " " + en_text, prev_fr + " " + fr_text)
        else:
            result.append((en_text, fr_text))

    return result


RATIO_THRESHOLD = 2.5  # Flag passages with EN/FR length ratio above this


def _balance_ratios(chunks: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Redistribute EN text between adjacent chunks to fix ratio mismatches.

    When EN and FR editions use different paragraph breaks, the proportional
    alignment can assign EN text to the wrong FR paragraph.  This shows up
    as adjacent chunks with complementary ratio problems:
      - chunk N:   FR is much longer than EN  (EN text missing)
      - chunk N+1: EN is much longer than FR  (has the extra EN text)

    Fix: move EN paragraphs from the start of chunk N+1 to the end of chunk N
    until the ratios balance.
    """
    if len(chunks) <= 1:
        return chunks

    result = list(chunks)
    changed = True

    # Iterate until no more improvements (usually 1-2 passes)
    for _ in range(3):
        if not changed:
            break
        changed = False

        for i in range(len(result) - 1):
            en_a, fr_a = result[i]
            en_b, fr_b = result[i + 1]

            len_en_a = len(en_a)
            len_fr_a = len(fr_a)
            len_en_b = len(en_b)
            len_fr_b = len(fr_b)

            if len_en_a == 0 or len_fr_a == 0 or len_en_b == 0 or len_fr_b == 0:
                continue

            ratio_a = len_fr_a / len_en_a  # > 1 means FR is longer
            ratio_b = len_en_b / len_fr_b  # > 1 means EN is longer

            # Pattern: chunk A has too little EN, chunk B has too much EN
            if ratio_a > RATIO_THRESHOLD and ratio_b > RATIO_THRESHOLD:
                # Try moving EN paragraphs from start of B to end of A
                # Split EN text of B on paragraph-like boundaries
                en_b_parts = re.split(r'(?<=\.\s)(?=[A-ZÀ-Ö])', en_b)
                if len(en_b_parts) <= 1:
                    continue

                # Greedily move parts from B to A until ratio_a improves
                best_split = 0
                best_score = abs(ratio_a - 1) + abs(ratio_b - 1)

                cumul = 0
                for j in range(1, len(en_b_parts)):
                    cumul += len(en_b_parts[j - 1])
                    new_en_a_len = len_en_a + cumul
                    new_en_b_len = len_en_b - cumul

                    if new_en_b_len < SHORT_THRESHOLD:
                        break  # Don't drain chunk B

                    new_ratio_a = len_fr_a / new_en_a_len if new_en_a_len > 0 else 999
                    new_ratio_b = new_en_b_len / len_fr_b if len_fr_b > 0 else 999

                    score = abs(new_ratio_a - 1) + abs(new_ratio_b - 1)
                    if score < best_score:
                        best_score = score
                        best_split = j

                if best_split > 0:
                    moved = "".join(en_b_parts[:best_split])
                    remaining = "".join(en_b_parts[best_split:])
                    result[i] = (en_a + " " + moved.strip(), fr_a)
                    result[i + 1] = (remaining.strip(), fr_b)
                    changed = True

            # Reverse pattern: chunk A has too much EN, chunk B has too little EN
            elif ratio_b > RATIO_THRESHOLD and ratio_a < 1 / RATIO_THRESHOLD:
                # Try moving EN paragraphs from end of A to start of B
                en_a_parts = re.split(r'(?<=\.\s)(?=[A-ZÀ-Ö])', en_a)
                if len(en_a_parts) <= 1:
                    continue

                best_split = len(en_a_parts)
                best_score = abs(1 / ratio_a - 1) + abs(ratio_b - 1)

                cumul = 0
                for j in range(len(en_a_parts) - 1, 0, -1):
                    cumul += len(en_a_parts[j])
                    new_en_a_len = len_en_a - cumul
                    new_en_b_len = len_en_b + cumul

                    if new_en_a_len < SHORT_THRESHOLD:
                        break

                    new_ratio_a = new_en_a_len / len_fr_a if len_fr_a > 0 else 999
                    new_ratio_b = len_fr_b / new_en_b_len if new_en_b_len > 0 else 999

                    score = abs(new_ratio_a - 1) + abs(new_ratio_b - 1)
                    if score < best_score:
                        best_score = score
                        best_split = j

                if best_split < len(en_a_parts):
                    kept = "".join(en_a_parts[:best_split])
                    moved = "".join(en_a_parts[best_split:])
                    result[i] = (kept.strip(), fr_a)
                    result[i + 1] = (moved.strip() + " " + en_b, fr_b)
                    changed = True

    return result


# ── Volume loading ───────────────────────────────────────────────────────────

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


# ── Text cleaning ────────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    """Normalize whitespace in text."""
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


# ── Vol 3 chapter boundary splitting ─────────────────────────────────────────

def _compute_fr_chapter_boundaries(fr_chapters: list[dict]) -> list[tuple[int, int, str]]:
    """Compute cumulative character boundaries for FR chapters.

    Returns list of (start_char, end_char, chapter_name) for the
    concatenated FR text.
    """
    boundaries = []
    cumul = 0
    for i, ch in enumerate(fr_chapters):
        text = ch.get("text", "")
        ch_name = ch.get("chapter", VOL3_FR_CHAPTER_NAMES[i] if i < len(VOL3_FR_CHAPTER_NAMES) else f"Part {i+1}")
        start = cumul
        cumul += len(text) + 2  # +2 for "\n\n" join separator
        boundaries.append((start, cumul, ch_name))
    return boundaries


def _assign_fr_chapter(
    fr_text_fragment: str,
    fr_cumul_pos: int,
    fr_boundaries: list[tuple[int, int, str]],
) -> str:
    """Determine which FR chapter a passage belongs to based on its
    position in the concatenated FR text."""
    for start, end, ch_name in fr_boundaries:
        if start <= fr_cumul_pos < end:
            return ch_name
    # Default to last chapter
    return fr_boundaries[-1][2] if fr_boundaries else "Unknown"


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Anchor-based bilingual alignment (no API calls needed)"
    )
    parser.add_argument("--test", action="store_true",
                        help="Run only on Vol 1 Overture for quick testing")
    parser.add_argument("--volume", type=int, default=None,
                        help="Run on a single volume only")
    parser.add_argument("--min-spacing", type=int, default=2000,
                        help="Minimum chars between anchors (default 2000)")
    args = parser.parse_args()

    print("Anchor-Based Bilingual Alignment (proper noun anchoring)")
    print("=" * 60)
    print("  No API calls needed — uses proper noun matching")
    print(f"  Min anchor spacing: {args.min_spacing} chars")

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

    # Filter volumes based on args
    vol_nums = sorted(set(en_volumes.keys()) & set(fr_volumes.keys()))
    if args.test:
        vol_nums = [1]
        print("\n  TEST MODE: Vol 1 Overture only")
    elif args.volume:
        if args.volume not in vol_nums:
            print(f"ERROR: Volume {args.volume} not found")
            return
        vol_nums = [args.volume]
        print(f"\n  Single volume mode: Vol {args.volume}")

    # ── Process each volume ──────────────────────────────────────────────

    all_records: list[dict] = []
    alignment_stats: list[dict] = []

    for vol_num in vol_nums:
        en_vol = en_volumes[vol_num]
        fr_vol = fr_volumes[vol_num]
        en_chapters = en_vol.get("chapters", [])
        fr_chapters = fr_vol.get("chapters", [])
        book_name = en_vol.get("book", "Unknown")

        # ── Vol 3 special handling ───────────────────────────────────────
        if vol_num in WHOLE_VOLUME_ALIGN:
            print(f"\n  Vol {vol_num}: Whole-volume alignment "
                  f"({len(en_chapters)} EN, {len(fr_chapters)} FR chapters)")

            en_combined = "\n\n".join(ch["text"] for ch in en_chapters)
            fr_combined = "\n\n".join(ch.get("text", "") for ch in fr_chapters)

            # Compute FR chapter boundaries for splitting output
            fr_boundaries = _compute_fr_chapter_boundaries(fr_chapters)

            # Extract anchors for stats
            en_anchors = extract_anchors(en_combined)
            fr_anchors = extract_anchors(fr_combined)
            anchor_pairs = lcs_anchor_pairs(
                en_anchors, fr_anchors, len(en_combined), len(fr_combined),
            )
            sparse_pairs = sparsify_anchors(anchor_pairs, args.min_spacing)

            print(f"    EN: {len(en_combined)} chars, {len(en_anchors)} anchors")
            print(f"    FR: {len(fr_combined)} chars, {len(fr_anchors)} anchors")
            print(f"    LCS anchor pairs: {len(anchor_pairs)}, "
                  f"after sparsify: {len(sparse_pairs)}")

            # Align
            pairs = align_chapter(en_combined, fr_combined)
            chunks = group_pairs_into_chunks(pairs)

            # Assign each chunk to a FR chapter based on cumulative FR position
            fr_cumul = 0
            for en_chunk, fr_chunk in chunks:
                ch_name = _assign_fr_chapter(fr_chunk, fr_cumul, fr_boundaries)
                # Find actual position of this FR chunk in the concatenated text
                fr_pos = fr_combined.find(fr_chunk[:50], max(0, fr_cumul - 100))
                if fr_pos >= 0:
                    ch_name = _assign_fr_chapter(fr_chunk, fr_pos, fr_boundaries)
                    fr_cumul = fr_pos + len(fr_chunk)
                else:
                    fr_cumul += len(fr_chunk)

                all_records.append({
                    "text": clean_text(en_chunk),
                    "text_fr": clean_text(fr_chunk),
                    "volume": vol_num,
                    "chapter": ch_name,
                    "book": book_name,
                })

            alignment_stats.append({
                "volume": vol_num,
                "chapter": "Full Volume",
                "en_chars": len(en_combined),
                "fr_chars": len(fr_combined),
                "anchor_pairs": len(sparse_pairs),
                "aligned_pairs": len(pairs),
                "output_chunks": len(chunks),
            })

            print(f"    → {len(chunks)} chunks")
            # Show chapter distribution
            ch_dist = Counter(r["chapter"] for r in all_records if r["volume"] == vol_num)
            for ch_name, count in sorted(ch_dist.items()):
                print(f"      {ch_name}: {count} chunks")

            continue

        # ── Normal per-chapter alignment ─────────────────────────────────
        for en_ch in en_chapters:
            ch_name = en_ch["chapter"]
            key = (vol_num, ch_name)

            # Test mode: only process Overture
            if args.test and ch_name != "Overture":
                continue

            fr_indices = EN_TO_FR_CHAPTER_MAP.get(key)

            if fr_indices is None:
                print(f"  WARNING: No FR mapping for {key}, skipping FR")
                en_paras = _filter_paragraphs(split_paragraphs(en_ch["text"]))
                for para_text in en_paras:
                    all_records.append({
                        "text": clean_text(para_text),
                        "text_fr": "",
                        "volume": vol_num,
                        "chapter": ch_name,
                        "book": book_name,
                    })
                continue

            # Combine FR chapter texts
            fr_texts = []
            for idx in fr_indices:
                if idx < len(fr_chapters):
                    fr_texts.append(fr_chapters[idx].get("text", ""))
                else:
                    print(f"  WARNING: FR chapter index {idx} out of range "
                          f"for Vol {vol_num} (has {len(fr_chapters)} chapters)")
            fr_combined = "\n\n".join(fr_texts)

            en_text = en_ch["text"]

            # Extract anchors for stats
            en_anchors = extract_anchors(en_text)
            fr_anchors = extract_anchors(fr_combined)
            anchor_pairs = lcs_anchor_pairs(
                en_anchors, fr_anchors, len(en_text), len(fr_combined),
            )
            sparse_pairs = sparsify_anchors(anchor_pairs, args.min_spacing)

            # Align
            pairs = align_chapter(en_text, fr_combined)
            chunks = group_pairs_into_chunks(pairs)

            # Build records
            for en_chunk, fr_chunk in chunks:
                all_records.append({
                    "text": clean_text(en_chunk),
                    "text_fr": clean_text(fr_chunk),
                    "volume": vol_num,
                    "chapter": ch_name,
                    "book": book_name,
                })

            stats = {
                "volume": vol_num,
                "chapter": ch_name,
                "en_chars": len(en_text),
                "fr_chars": len(fr_combined),
                "anchor_pairs": len(sparse_pairs),
                "aligned_pairs": len(pairs),
                "output_chunks": len(chunks),
            }
            alignment_stats.append(stats)

            print(f"  Vol {vol_num}, {ch_name}: "
                  f"{len(en_anchors)} EN anchors, {len(fr_anchors)} FR anchors, "
                  f"{len(sparse_pairs)} pairs → {len(chunks)} chunks")

    # ── Re-index and save ────────────────────────────────────────────────

    print(f"\n--- Results ---")

    for i, r in enumerate(all_records, start=1):
        r["index"] = i

    print(f"Total passages: {len(all_records)}")
    has_fr = sum(1 for r in all_records if r["text_fr"])
    print(f"With French text: {has_fr}/{len(all_records)} "
          f"({has_fr / len(all_records) * 100:.1f}%)")

    # Length stats
    en_lens = [len(r["text"]) for r in all_records]
    fr_lens = [len(r["text_fr"]) for r in all_records if r["text_fr"]]
    if en_lens:
        avg_en = sum(en_lens) / len(en_lens)
        print(f"EN length: avg={avg_en:.0f}, min={min(en_lens)}, max={max(en_lens)}")
    if fr_lens:
        avg_fr = sum(fr_lens) / len(fr_lens)
        print(f"FR length: avg={avg_fr:.0f}, min={min(fr_lens)}, max={max(fr_lens)}")

    # Length ratio analysis
    ratios = []
    bad_ratios = 0
    for r in all_records:
        en_len = len(r["text"])
        fr_len = len(r["text_fr"])
        if en_len > 0 and fr_len > 0:
            ratio = max(en_len, fr_len) / min(en_len, fr_len)
            ratios.append(ratio)
            if ratio > 3.0:
                bad_ratios += 1
    if ratios:
        avg_ratio = sum(ratios) / len(ratios)
        sorted_ratios = sorted(ratios)
        median_ratio = sorted_ratios[len(sorted_ratios) // 2]
        print(f"Length ratios: avg={avg_ratio:.2f}, "
              f"median={median_ratio:.2f}, "
              f">3x: {bad_ratios}/{len(ratios)} ({bad_ratios/len(ratios)*100:.1f}%)")

    # Verify opening lines
    if all_records:
        first = all_records[0]
        print(f"\nFirst EN: {first['text'][:80]}...")
        print(f"First FR: {first['text_fr'][:80]}...")

    # Save main output
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)
    print(f"\nSaved {len(all_records)} passages to: {OUTPUT_PATH}")

    # Save stats
    with open(ALIGNED_SENTS_PATH, "w", encoding="utf-8") as f:
        json.dump(alignment_stats, f, indent=2)
    print(f"Stats saved to: {ALIGNED_SENTS_PATH}")

    # Per-volume summary
    print(f"\n=== Per-Volume Summary ===")
    vol_counts = Counter(r["volume"] for r in all_records)
    for vol in sorted(vol_counts):
        vol_fr = sum(1 for r in all_records
                     if r["volume"] == vol and r["text_fr"])
        vol_stats = [s for s in alignment_stats if s["volume"] == vol]
        total_anchors = sum(s.get("anchor_pairs", 0) for s in vol_stats)
        print(f"  Vol {vol}: {vol_counts[vol]} passages, "
              f"{vol_fr} with FR, {total_anchors} anchor pairs")


if __name__ == "__main__":
    main()
