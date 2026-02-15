"""
Corpus loading and table-of-contents builder for the Read Proust feature.

Loads parsed_clean_bilingual.json once at import time and provides lookup
functions for browsing volumes, chapters, and paginated passages.
"""

import json
from pathlib import Path
from collections import OrderedDict

from text_utils import clean_passage_text

# ── French name translations ──────────────────────────────────────────────────
_FRENCH_NAMES = {
    # Volume names
    "Swann's Way": "Du côté de chez Swann",
    "Within a Budding Grove": "À l\u2019ombre des jeunes filles en fleurs",
    "The Guermantes Way": "Le Côté de Guermantes",
    "Sodom and Gomorrah": "Sodome et Gomorrhe",
    "Cities of the Plain": "Sodome et Gomorrhe",
    "The Captive": "La Prisonnière",
    "The Fugitive": "Albertine disparue",
    "The Sweet Cheat Gone": "Albertine disparue",
    "Time Regained": "Le Temps retrouvé",
    # Chapter names (Vol 1)
    "Overture": "Combray",
    "Swann in Love": "Un amour de Swann",
    "Place-Names: The Name": "Noms de pays : le nom",
    # Chapter names (Vol 2)
    "Madame Swann at Home": "Autour de Mme Swann",
    "Place-Names: The Place": "Noms de pays : le pays",
    "Seascape, with Frieze of Girls": "Autour de Mme Swann (suite)",
    # Vol 3 part names
    "Part 1": "Première partie",
    "Part 2": "Deuxième partie",
    "Part 3": "Troisième partie",
    # Vol 3-7: generic chapter names
    "Chapter 1": "Chapitre 1",
    "Chapter 2": "Chapitre 2",
    "Chapter 3": "Chapitre 3",
    "Chapter 4": "Chapitre 4",
    # Vol 4 specific
    "Introduction": "Introduction",
    # Vol 5 named chapters
    "Chapter 1 — Life with Albertine": "Chapitre 1 — Vie en commun avec Albertine",
    "Chapter 2 — The Verdurins Quarrel with M. De Charlus": "Chapitre 2 — Les Verdurin se brouillent avec M. de Charlus",
    "Chapter 3 — Flight of Albertine": "Chapitre 3 — Disparition d\u2019Albertine",
    # Vol 6
    "Chapter 1 — Grief and Oblivion": "Chapitre 1 — Le chagrin et l\u2019oubli",
    "Chapter 2 — Mademoiselle De Forcheville": "Chapitre 2 — Mademoiselle de Forcheville",
    "Chapter 3 — Venice": "Chapitre 3 — Séjour à Venise",
    "Chapter 4 — A Fresh Light Upon Robert De Saint-Loup": "Chapitre 4 — Nouvel aspect de Robert de Saint-Loup",
    # Vol 7
    "Chapter 1 — Tansonville": "Chapitre 1 — Tansonville",
    "Chapter 2 — M. de Charlus During the War, His Opinions, His Pleasures": "Chapitre 2 — M. de Charlus pendant la guerre",
    "Chapter 3 — An Afternoon Party at the House of the Princesse de Guermantes": "Chapitre 3 — Matinée chez la princesse de Guermantes",
}


def _fr_name(en_name: str) -> str:
    """Translate an English volume/chapter name to French, falling back to the original."""
    # Normalize curly apostrophes to straight for consistent lookup
    normalized = en_name.replace("\u2019", "'")
    return _FRENCH_NAMES.get(en_name) or _FRENCH_NAMES.get(normalized, en_name)


_DATA_PATH = Path(__file__).parent / "parsed_clean_bilingual.json"

# Loaded once at startup
_passages: list[dict] = []

# volume number -> { chapter_name -> [passage indices into _passages] }
_structure: OrderedDict[int, OrderedDict[str, list[int]]] = OrderedDict()

# Ordered list of (volume, chapter) for prev/next navigation
_chapter_order: list[tuple[int, str]] = []

# Reverse lookup: passage "index" field value -> position in _passages array
_index_to_pos: dict[int, int] = {}


def _load():
    global _passages, _structure, _chapter_order, _index_to_pos
    with open(_DATA_PATH, encoding="utf-8") as f:
        _passages = json.load(f)

    # Build volume -> chapter -> passage indices, preserving document order
    for idx, p in enumerate(_passages):
        vol = p.get("volume", 1)
        chapter = p.get("chapter", "Unknown")
        if vol not in _structure:
            _structure[vol] = OrderedDict()
        if chapter not in _structure[vol]:
            _structure[vol][chapter] = []
        _structure[vol][chapter].append(idx)

        # Build reverse lookup from passage index field to array position
        passage_index = p.get("index")
        if passage_index is not None:
            _index_to_pos[passage_index] = idx

    # Build ordered chapter list
    _chapter_order = [
        (vol, ch) for vol in _structure for ch in _structure[vol]
    ]


# Load on import
_load()


def get_table_of_contents(lang: str = "en") -> list[dict]:
    """
    Return the full table of contents.

    Args:
        lang: "en" for English names, "fr" for French names.

    Returns a list of volumes, each with chapters, passage counts,
    and index ranges.
    """
    toc = []
    for vol_num, chapters in _structure.items():
        first_passage = _passages[chapters[next(iter(chapters))][0]]
        vol_name = first_passage.get("book", f"Volume {vol_num}")
        if lang == "fr":
            vol_name = _fr_name(vol_name)

        chapter_list = []
        for ch_name, indices in chapters.items():
            display_name = _fr_name(ch_name) if lang == "fr" else ch_name
            chapter_list.append({
                "name": ch_name,
                "display_name": display_name,
                "passage_count": len(indices),
                "first_index": indices[0],
                "last_index": indices[-1],
            })

        toc.append({
            "volume": vol_num,
            "volume_name": vol_name,
            "chapter_count": len(chapters),
            "total_passages": sum(len(v) for v in chapters.values()),
            "chapters": chapter_list,
        })
    return toc


def get_chapter_passages(
    volume: int,
    chapter: str,
    offset: int = 0,
    limit: int = 20,
    lang: str = "en",
) -> dict | None:
    """
    Return paginated passages for a given volume/chapter.

    Args:
        lang: "en" for English text, "fr" for French text, "both" for both.

    Returns None if the volume/chapter combination is not found.
    """
    if volume not in _structure or chapter not in _structure[volume]:
        return None

    indices = _structure[volume][chapter]
    total = len(indices)
    page_indices = indices[offset : offset + limit]

    passages = []
    for idx in page_indices:
        p = _passages[idx]
        entry = {
            "book": p.get("book", "Unknown"),
            "chapter": p.get("chapter", "Unknown"),
            "volume": p.get("volume", volume),
            "index": p.get("index", idx),
        }

        if lang == "fr":
            fr_text = p.get("text_fr")
            entry["text"] = fr_text if fr_text else clean_passage_text(p.get("text", ""))
            entry["text_unavailable"] = fr_text is None
        elif lang == "both":
            entry["text"] = clean_passage_text(p.get("text", ""))
            entry["text_fr"] = p.get("text_fr")
        else:
            entry["text"] = clean_passage_text(p.get("text", ""))

        passages.append(entry)

    first_passage = _passages[indices[0]]
    vol_name = first_passage.get("book", f"Volume {volume}")
    vol_name_en = vol_name
    chapter_display = chapter
    chapter_display_en = chapter
    if lang in ("fr", "both"):
        vol_name = _fr_name(vol_name)
        chapter_display = _fr_name(chapter)

    # Determine prev/next chapters
    current_pos = _chapter_order.index((volume, chapter))
    prev_chapter = _chapter_order[current_pos - 1] if current_pos > 0 else None
    next_chapter = (
        _chapter_order[current_pos + 1]
        if current_pos < len(_chapter_order) - 1
        else None
    )

    return {
        "passages": passages,
        "total_in_chapter": total,
        "offset": offset,
        "limit": limit,
        "has_next": offset + limit < total,
        "has_prev": offset > 0,
        "volume_name": vol_name,
        "chapter_name": chapter_display,
        **({"volume_name_en": vol_name_en, "chapter_name_en": chapter_display_en} if lang == "both" else {}),
        "prev_chapter": (
            {"volume": prev_chapter[0], "chapter": prev_chapter[1]}
            if prev_chapter
            else None
        ),
        "next_chapter": (
            {"volume": next_chapter[0], "chapter": next_chapter[1]}
            if next_chapter
            else None
        ),
    }


def get_total_passages() -> int:
    """Return total number of passages in the corpus."""
    return len(_passages)


def get_passage_text(passage_index: int, lang: str = "en") -> dict | None:
    """
    Get the text of a single passage by its index.

    Args:
        passage_index: The passage index field value.
        lang: "en" for English, "fr" for French, "both" for both.

    Returns dict with text field(s) or None if not found.
    """
    pos = _index_to_pos.get(passage_index)
    if pos is None:
        return None

    p = _passages[pos]
    result = {
        "index": passage_index,
        "book": p.get("book", "Unknown"),
        "chapter": p.get("chapter", "Unknown"),
    }

    if lang == "fr":
        fr_text = p.get("text_fr")
        result["text"] = fr_text if fr_text else clean_passage_text(p.get("text", ""))
        result["text_unavailable"] = fr_text is None
    elif lang == "both":
        result["text"] = clean_passage_text(p.get("text", ""))
        result["text_fr"] = p.get("text_fr")
    else:
        result["text"] = clean_passage_text(p.get("text", ""))

    return result


def search_passages_by_text(
    substring: str,
    volume: int | None = None,
    limit: int = 10,
    lang: str = "en",
) -> list[dict]:
    """
    In-memory case-insensitive text search across the corpus.

    Returns a list of passage dicts matching the substring, optionally
    filtered to a specific volume.  No API calls — purely local.
    """
    needle = substring.lower()
    results: list[dict] = []

    for idx, p in enumerate(_passages):
        if volume is not None and p.get("volume") != volume:
            continue

        # Search in the appropriate language text
        if lang == "fr":
            text = p.get("text_fr", "") or ""
        else:
            text = p.get("text", "")

        if needle in text.lower():
            entry = {
                "index": p.get("index", idx),
                "book": p.get("book", "Unknown"),
                "chapter": p.get("chapter", "Unknown"),
                "volume": p.get("volume"),
                "text": clean_passage_text(text)[:500],
            }
            results.append(entry)
            if len(results) >= limit:
                break

    return results


def locate_passage(passage_index: int) -> dict | None:
    """
    Given a passage index, return its location in the reading view.

    Returns { volume, chapter, page, passageIndex } or None if not found.
    The page is computed as (position within chapter) // PASSAGES_PER_PAGE.
    """
    pos = _index_to_pos.get(passage_index)
    if pos is None:
        return None

    p = _passages[pos]
    vol = p.get("volume", 1)
    chapter = p.get("chapter", "Unknown")

    if vol not in _structure or chapter not in _structure[vol]:
        return None

    chapter_indices = _structure[vol][chapter]
    position_in_chapter = chapter_indices.index(pos)
    page = position_in_chapter // 20  # matches PASSAGES_PER_PAGE in ReadingView

    return {
        "volume": vol,
        "chapter": chapter,
        "page": page,
        "passageIndex": passage_index,
    }
