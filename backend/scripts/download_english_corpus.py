"""
Download Proust's English text from Standard Ebooks (Vols 1-6) and
Project Gutenberg Australia (Vol 7).

Standard Ebooks provides clean, professionally formatted XHTML from the
C.K. Scott Moncrieff translation. Volume 7 uses Stephen Hudson's translation
from Project Gutenberg Australia.

Preserves *italic* and **bold** formatting as markdown-style markers.

Usage:
    cd backend
    python scripts/download_english_corpus.py
"""

import json
import re
import time
from html import unescape
from pathlib import Path

import requests

DATA_DIR = Path(__file__).parent.parent / "data" / "english_raw"
DATA_DIR.mkdir(parents=True, exist_ok=True)

SE_BASE = (
    "https://raw.githubusercontent.com/standardebooks/"
    "marcel-proust_in-search-of-lost-time_c-k-scott-moncrieff/"
    "master/src/epub/text/"
)
PG_AU_URL = "https://gutenberg.net.au/ebooks03/0300691h.html"

HEADERS = {
    "User-Agent": "ProustGPT/1.0 (educational project) python-requests",
}

# ── Volume mapping ──────────────────────────────────────────────────────────
# Each entry maps SE XHTML files to the chapter names used in the existing
# corpus (parsed_clean.json). When multiple SE files map to one chapter,
# their texts are concatenated.

VOLUMES = [
    {
        "volume": 1,
        "book": "Swann\u2019s Way",
        "chapters": [
            {
                "name": "Overture",
                "files": ["chapter-1-1.xhtml", "chapter-1-2.xhtml"],
            },
            {
                "name": "Swann in Love",
                "files": ["chapter-1-3.xhtml"],
            },
            {
                "name": "Place-Names: The Name",
                "files": ["chapter-1-4.xhtml"],
            },
        ],
    },
    {
        "volume": 2,
        "book": "Within a Budding Grove",
        "chapters": [
            {
                "name": "Madame Swann at Home",
                "files": ["chapter-2-1-1.xhtml"],
            },
            {
                "name": "Place-Names: The Place",
                "files": ["chapter-2-1-2.xhtml", "chapter-2-2-1.xhtml"],
            },
            {
                "name": "Seascape, with Frieze of Girls",
                "files": ["chapter-2-2-2.xhtml"],
            },
        ],
    },
    {
        "volume": 3,
        "book": "The Guermantes Way",
        "chapters": [
            {
                "name": "Part 1",
                "files": ["chapter-3-1-1.xhtml"],
            },
            {
                "name": "Part 2",
                "files": ["chapter-3-2-1.xhtml"],
            },
            {
                "name": "Part 3",
                "files": ["chapter-3-2-2.xhtml"],
            },
        ],
    },
    {
        "volume": 4,
        "book": "Cities of the Plain",
        "chapters": [
            {
                "name": "Introduction",
                "files": ["prologue-4-1.xhtml"],
            },
            {
                "name": "Chapter 1",
                "files": ["chapter-4-1-1.xhtml"],
            },
            {
                "name": "Chapter 2",
                "files": ["chapter-4-1-2.xhtml", "chapter-4-2-2.xhtml"],
            },
            {
                "name": "Chapter 3",
                "files": ["chapter-4-2-3.xhtml"],
            },
            {
                "name": "Chapter 4",
                "files": ["chapter-4-2-4.xhtml"],
            },
        ],
    },
    {
        "volume": 5,
        "book": "The Captive",
        "chapters": [
            {
                "name": "Chapter 1 \u2014 Life with Albertine",
                "files": ["chapter-5-1-1.xhtml"],
            },
            {
                "name": "Chapter 2 \u2014 The Verdurins Quarrel with M. De Charlus",
                "files": ["chapter-5-1-2.xhtml", "chapter-5-2-2.xhtml"],
            },
            {
                "name": "Chapter 3 \u2014 Flight of Albertine",
                "files": ["chapter-5-2-3.xhtml"],
            },
        ],
    },
    {
        "volume": 6,
        "book": "The Sweet Cheat Gone",
        "chapters": [
            {
                "name": "Chapter 1 \u2014 Grief and Oblivion",
                "files": ["chapter-6-1.xhtml"],
            },
            {
                "name": "Chapter 2 \u2014 Mademoiselle De Forcheville",
                "files": ["chapter-6-2.xhtml"],
            },
            {
                "name": "Chapter 3 \u2014 Venice",
                "files": ["chapter-6-3.xhtml"],
            },
            {
                "name": "Chapter 4 \u2014 A Fresh Light Upon Robert De Saint-Loup",
                "files": ["chapter-6-4.xhtml"],
            },
        ],
    },
]


# ── XHTML → text conversion ────────────────────────────────────────────────


def xhtml_to_text(html: str) -> str:
    """Convert Standard Ebooks XHTML to clean text with markdown formatting.

    Preserves:
      - *italic* from <i>, <em> tags
      - **bold** from <b>, <strong> tags
      - Paragraph breaks as double newlines
      - Proper punctuation and special characters
    """
    # Remove everything outside the <body> (or <section>) content
    body_match = re.search(r"<body[^>]*>(.*)</body>", html, re.DOTALL)
    if body_match:
        text = body_match.group(1)
    else:
        text = html

    # Remove <header> blocks (chapter titles, headings inside the content)
    text = re.sub(r"<header[^>]*>.*?</header>", "", text, flags=re.DOTALL)
    # Remove standalone heading tags (h1-h6)
    text = re.sub(r"<h[1-6][^>]*>.*?</h[1-6]>", "", text, flags=re.DOTALL)

    # Remove <figure>, <figcaption>, <table> blocks
    text = re.sub(r"<figure[^>]*>.*?</figure>", "", text, flags=re.DOTALL)
    text = re.sub(r"<table[^>]*>.*?</table>", "", text, flags=re.DOTALL)

    # Remove footnote/endnote references
    text = re.sub(r'<a[^>]*epub:type="noteref"[^>]*>.*?</a>', "", text, flags=re.DOTALL)

    # Convert <br> to newlines
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)

    # Preserve bold: <b>, <strong> → **text**
    text = re.sub(
        r"<(b|strong)\b[^>]*>(.*?)</\1>", r"**\2**", text, flags=re.DOTALL
    )

    # Preserve italic: <i>, <em> → *text*
    # SE uses <i epub:type="..."> for titles, foreign words, etc.
    text = re.sub(
        r"<(i|em)\b[^>]*>(.*?)</\1>", r"*\2*", text, flags=re.DOTALL
    )

    # Convert <p> → double newline boundaries
    text = re.sub(r"</p>", "\n\n", text)
    text = re.sub(r"<p[^>]*>", "", text)

    # Convert block-level elements to newlines
    text = re.sub(r"</(div|section|blockquote)>", "\n\n", text)
    text = re.sub(r"<(div|section|blockquote)[^>]*>", "", text)

    # Remove all remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Unescape HTML entities
    text = unescape(text)

    # Clean up whitespace
    text = re.sub(r"[ \t]+", " ", text)          # collapse horizontal space
    text = re.sub(r" *\n *", "\n", text)          # strip spaces around newlines
    text = re.sub(r"\n{3,}", "\n\n", text)        # collapse 3+ newlines to 2
    text = text.strip()

    # Fix doubled italic markers from nested tags: ***text*** → *text*
    text = re.sub(r"\*{3,}([^*]+)\*{3,}", r"*\1*", text)
    # Fix empty italic markers: ** → (remove)
    text = re.sub(r"\*{2,}(?=\s|$)", "", text)
    text = re.sub(r"(?:^|\s)\*{2,}", lambda m: m.group(0).replace("*", ""), text)

    return text


# ── PG Australia Vol 7 parsing ──────────────────────────────────────────────


def pg_html_to_chapters(html: str) -> list[dict]:
    """Parse Project Gutenberg Australia HTML for Time Regained into chapters.

    PG Australia uses paired headings per chapter:
      <h3>CHAPTER I</h3><h3>TANSONVILLE</h3>
    followed by the chapter body text.

    Returns list of {name, text} dicts.
    """
    # Find all heading tags and their positions
    heading_pattern = re.compile(
        r"<h[2-4][^>]*>(.*?)</h[2-4]>", re.DOTALL | re.IGNORECASE
    )
    raw_headings = list(heading_pattern.finditer(html))

    # Identify "CHAPTER I/II/III" headings as chapter start markers
    chapter_starts = []
    for i, h in enumerate(raw_headings):
        heading_text = re.sub(r"<[^>]+>", "", h.group(1)).strip()
        if re.match(r"^CHAPTER\s+[IVX]+$", heading_text, re.IGNORECASE):
            chapter_starts.append(i)

    chapter_names = [
        "Chapter 1 \u2014 Tansonville",
        "Chapter 2 \u2014 M. de Charlus During the War, His Opinions, His Pleasures",
        "Chapter 3 \u2014 An Afternoon Party at the House of the Princesse de Guermantes",
    ]

    chapters = []
    for ci, heading_idx in enumerate(chapter_starts):
        # Content starts after the subtitle heading (the one after "CHAPTER X")
        # Skip the subtitle heading too
        subtitle_idx = heading_idx + 1
        if subtitle_idx < len(raw_headings):
            start = raw_headings[subtitle_idx].end()
        else:
            start = raw_headings[heading_idx].end()

        # Content ends at the next chapter start heading, or end of document
        if ci + 1 < len(chapter_starts):
            end = raw_headings[chapter_starts[ci + 1]].start()
        else:
            # Find "THE END" heading or use end of HTML
            end = len(html)
            for h in raw_headings:
                h_text = re.sub(r"<[^>]+>", "", h.group(1)).strip()
                if h_text.upper() == "THE END":
                    end = h.start()
                    break

        chapter_html = html[start:end]

        # Convert formatting
        chapter_html = re.sub(r"<(i|em)\b[^>]*>(.*?)</\1>", r"*\2*", chapter_html, flags=re.DOTALL)
        chapter_html = re.sub(r"<(b|strong)\b[^>]*>(.*?)</\1>", r"**\2**", chapter_html, flags=re.DOTALL)
        chapter_html = re.sub(r"<br\s*/?>", "\n", chapter_html, flags=re.IGNORECASE)
        chapter_html = re.sub(r"</p>", "\n\n", chapter_html)
        chapter_html = re.sub(r"<p[^>]*>", "", chapter_html)

        # Remove remaining HTML
        chapter_text = re.sub(r"<[^>]+>", "", chapter_html)
        chapter_text = unescape(chapter_text)

        # Clean whitespace
        chapter_text = re.sub(r"[ \t]+", " ", chapter_text)
        chapter_text = re.sub(r" *\n *", "\n", chapter_text)
        chapter_text = re.sub(r"\n{3,}", "\n\n", chapter_text)
        chapter_text = chapter_text.strip()

        if not chapter_text or len(chapter_text) < 200:
            continue

        name = chapter_names[len(chapters)] if len(chapters) < len(chapter_names) else f"Chapter {len(chapters) + 1}"
        chapters.append({"name": name, "text": chapter_text})

    return chapters


def _is_pg_boilerplate(text: str) -> bool:
    """Check if text is PG Australia boilerplate rather than novel content."""
    lower = text[:500].lower()
    return any(phrase in lower for phrase in [
        "project gutenberg",
        "this etext",
        "this ebook",
        "distributed proofreaders",
        "copyright",
        "end of the project",
        "start of the project",
    ])


# ── Download helpers ────────────────────────────────────────────────────────


def fetch_se_chapter(filename: str) -> str | None:
    """Fetch a single XHTML chapter from Standard Ebooks GitHub."""
    url = SE_BASE + filename
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"    Error fetching {filename}: {e}")
        return None


def download_se_volume(vol_info: dict) -> dict:
    """Download all chapters for a Standard Ebooks volume."""
    volume_num = vol_info["volume"]
    book = vol_info["book"]
    print(f"\n{'='*60}")
    print(f"Volume {volume_num}: {book}")
    print(f"{'='*60}")

    chapters = []
    for ch_info in vol_info["chapters"]:
        ch_name = ch_info["name"]
        files = ch_info["files"]
        print(f"  {ch_name} ({len(files)} file(s))...")

        texts = []
        for fname in files:
            print(f"    Fetching {fname}...")
            html = fetch_se_chapter(fname)
            time.sleep(0.5)  # Rate limiting
            if html:
                text = xhtml_to_text(html)
                if text and len(text) > 100:
                    texts.append(text)
                    print(f"      -> {len(text):,} chars")
                else:
                    print(f"      -> Too short or empty")
            else:
                print(f"      -> Failed")

        if texts:
            merged = "\n\n".join(texts)
            chapters.append({
                "chapter": ch_name,
                "text": merged,
                "char_count": len(merged),
                "source_files": files,
            })
            print(f"    Total: {len(merged):,} chars")

    return {
        "volume": volume_num,
        "book": book,
        "chapter_count": len(chapters),
        "total_chars": sum(ch["char_count"] for ch in chapters),
        "chapters": chapters,
    }


def download_pg_volume7() -> dict:
    """Download Volume 7 from Project Gutenberg Australia."""
    print(f"\n{'='*60}")
    print(f"Volume 7: Time Regained (PG Australia)")
    print(f"{'='*60}")

    print(f"  Fetching {PG_AU_URL}...")
    try:
        resp = requests.get(PG_AU_URL, headers=HEADERS, timeout=60)
        resp.raise_for_status()
        html = resp.text
        print(f"  Downloaded {len(html):,} chars of HTML")
    except Exception as e:
        print(f"  Error: {e}")
        return {
            "volume": 7,
            "book": "Time Regained",
            "chapter_count": 0,
            "total_chars": 0,
            "chapters": [],
        }

    chapters = pg_html_to_chapters(html)
    print(f"  Found {len(chapters)} chapters")
    for ch in chapters:
        print(f"    {ch['name']}: {len(ch['text']):,} chars")

    return {
        "volume": 7,
        "book": "Time Regained",
        "chapter_count": len(chapters),
        "total_chars": sum(len(ch["text"]) for ch in chapters),
        "chapters": [
            {
                "chapter": ch["name"],
                "text": ch["text"],
                "char_count": len(ch["text"]),
                "source_files": ["PG-AU-0300691h.html"],
            }
            for ch in chapters
        ],
    }


def main():
    print("Downloading Proust's English text")
    print("Standard Ebooks (Vols 1-6) + PG Australia (Vol 7)\n")

    # Download Vols 1-6 from Standard Ebooks
    for vol_info in VOLUMES:
        result = download_se_volume(vol_info)

        output_path = DATA_DIR / f"volume_{vol_info['volume']}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"\n  Saved to {output_path}")
        print(f"  {result['chapter_count']} chapters, {result['total_chars']:,} chars total")

    # Download Vol 7 from PG Australia
    result7 = download_pg_volume7()
    output_path = DATA_DIR / "volume_7.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result7, f, ensure_ascii=False, indent=2)
    print(f"\n  Saved to {output_path}")
    print(f"  {result7['chapter_count']} chapters, {result7['total_chars']:,} chars total")

    # Summary
    print(f"\n\n{'='*60}")
    print("Download complete!")
    print(f"Files saved to: {DATA_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
