"""
Corpus loading and table-of-contents builder for the Read Proust feature.

Loads parsed_clean.json once at import time and provides lookup functions
for browsing volumes, chapters, and paginated passages.
"""

import json
from pathlib import Path
from collections import OrderedDict

from text_utils import clean_passage_text

_DATA_PATH = Path(__file__).parent / "parsed_clean.json"

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


def get_table_of_contents() -> list[dict]:
    """
    Return the full table of contents.

    Returns a list of volumes, each with chapters, passage counts,
    and index ranges.
    """
    toc = []
    for vol_num, chapters in _structure.items():
        first_passage = _passages[chapters[next(iter(chapters))][0]]
        vol_name = first_passage.get("book", f"Volume {vol_num}")

        chapter_list = []
        for ch_name, indices in chapters.items():
            chapter_list.append({
                "name": ch_name,
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
) -> dict | None:
    """
    Return paginated passages for a given volume/chapter.

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
        passages.append({
            "book": p.get("book", "Unknown"),
            "chapter": p.get("chapter", "Unknown"),
            "text": clean_passage_text(p.get("text", "")),
            "volume": p.get("volume", volume),
            "index": p.get("index", idx),
        })

    first_passage = _passages[indices[0]]
    vol_name = first_passage.get("book", f"Volume {volume}")

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
        "chapter_name": chapter,
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
