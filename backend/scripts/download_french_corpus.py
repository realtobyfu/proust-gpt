"""
Download Proust's French text from Wikisource via the MediaWiki API.

All seven volumes of "À la recherche du temps perdu" are in the public domain.
This script fetches each chapter/section and saves the raw text to
backend/data/french_raw/ as JSON files per volume.

Uses action=parse (not action=query+extracts) because Wikisource pages
use transclusion from the Page: namespace.

Usage:
    cd backend
    python scripts/download_french_corpus.py
"""

import json
import re
import time
from html import unescape
from pathlib import Path

import requests

DATA_DIR = Path(__file__).parent.parent / "data" / "french_raw"
DATA_DIR.mkdir(parents=True, exist_ok=True)

API_URL = "https://fr.wikisource.org/w/api.php"
HEADERS = {
    "User-Agent": "ProustGPT/1.0 (educational project) python-requests",
}

# ── Volume mapping ──────────────────────────────────────────────────────────
# Chapter page titles discovered from the Wikisource allpages API.
# "Texte entier" and "Sommaire" pages are excluded.
# For volumes without subpages (vol 2), we fetch the main page.

VOLUMES = [
    {
        "volume": 1,
        "title_en": "Swann's Way",
        "title_fr": "Du côté de chez Swann",
        "wikisource_root": "Du côté de chez Swann",
        "chapters": [
            "Du côté de chez Swann/Partie 1",
            "Du côté de chez Swann/Partie 2",
            "Du côté de chez Swann/Partie 3",
        ],
    },
    {
        "volume": 2,
        "title_en": "Within a Budding Grove",
        "title_fr": "À l\u2019ombre des jeunes filles en fleurs",
        "wikisource_root": "À l\u2019ombre des jeunes filles en fleurs",
        "chapters": [
            "À l\u2019ombre des jeunes filles en fleurs/Première partie",
            "À l\u2019ombre des jeunes filles en fleurs/Deuxième partie",
            "À l\u2019ombre des jeunes filles en fleurs/Troisième partie",
        ],
    },
    {
        "volume": 3,
        "title_en": "The Guermantes Way",
        "title_fr": "Le Côté de Guermantes",
        "wikisource_root": "Le Côté de Guermantes",
        "chapters": [
            "Le Côté de Guermantes/Première partie",
            "Le Côté de Guermantes/Deuxième partie",
            "Le Côté de Guermantes/Troisième partie",
        ],
    },
    {
        "volume": 4,
        "title_en": "Sodom and Gomorrah",
        "title_fr": "Sodome et Gomorrhe",
        "wikisource_root": "Sodome et Gomorrhe",
        "chapters": [
            "Sodome et Gomorrhe/Partie 1",
            "Sodome et Gomorrhe/Partie 2 - chapitre 1",
            "Sodome et Gomorrhe/Partie 2 - chapitre 2",
            "Sodome et Gomorrhe/Partie 2 - chapitre 3",
            "Sodome et Gomorrhe/Partie 2 - chapitre 4",
        ],
    },
    {
        "volume": 5,
        "title_en": "The Captive",
        "title_fr": "La Prisonnière",
        "wikisource_root": "La Prisonnière",
        "chapters": [
            "La Prisonnière/Chapitre 1",
            "La Prisonnière/Chapitre 2",
            "La Prisonnière/Chapitre 3",
        ],
    },
    {
        "volume": 6,
        "title_en": "The Fugitive",
        "title_fr": "Albertine disparue",
        "wikisource_root": "Albertine disparue",
        "chapters": [
            "Albertine disparue/Chapitre I",
            "Albertine disparue/Chapitre II",
            "Albertine disparue/Chapitre III",
            "Albertine disparue/Chapitre IV",
        ],
    },
    {
        "volume": 7,
        "title_en": "Time Regained",
        "title_fr": "Le Temps retrouvé",
        "wikisource_root": "Le Temps retrouvé",
        "chapters": [
            "Le Temps retrouvé/I",
            "Le Temps retrouvé/II",
            "Le Temps retrouvé/III",
        ],
    },
]


def html_to_text(html: str) -> str:
    """Convert rendered Wikisource HTML to clean plain text."""
    # Remove the header/metadata box (ws-header, headertemplate, etc.)
    text = re.sub(
        r'<div\b[^>]*class="[^"]*ws-header[^"]*"[^>]*>.*?</div>\s*</div>',
        "", html, flags=re.DOTALL,
    )
    text = re.sub(
        r'<table\b[^>]*class="[^"]*headertemplate[^"]*"[^>]*>.*?</table>',
        "", text, flags=re.DOTALL,
    )
    # Remove navigation links (previous/next chapter)
    text = re.sub(
        r'<div\b[^>]*class="[^"]*ws-noexport[^"]*"[^>]*>.*?</div>',
        "", text, flags=re.DOTALL,
    )
    # Remove script/style tags and content
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", text, flags=re.DOTALL)
    # Remove reference tags
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.DOTALL)
    text = re.sub(r"<ref[^/]*/?>", "", text)
    # Preserve italic/emphasis as *text*
    text = re.sub(r"<(i|em)\b[^>]*>(.*?)</\1>", r"*\2*", text, flags=re.DOTALL)
    # Replace <br> with newlines
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    # Replace paragraph tags with double newlines
    text = re.sub(r"</p>", "\n\n", text)
    text = re.sub(r"<p[^>]*>", "", text)
    # Remove all remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Unescape HTML entities
    text = unescape(text)
    # Clean up whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    # Remove Wikisource header boilerplate (bibliographic metadata before actual text)
    # e.g. "À la recherche du temps perdu (1913)Gallimard, 1946 (tome 1, p. 10-251)."
    text = re.sub(
        r"^À la recherche du temps perdu \(\d{4}\)[^\n]*\(tome[^\)]+\)\.\s*",
        "", text, count=1,
    )
    # Remove chapter navigation remnants like "Troisième partie  ►"
    text = re.sub(r"^[^\n]*[►◄]\s*", "", text)
    text = text.strip()
    # Clean Wikisource artifacts from the body text
    text = clean_french_artifacts(text)
    return text


def clean_french_artifacts(text: str) -> str:
    """Strip Wikisource structural artifacts from French chapter text.

    Removes publication metadata, part/chapter headers, italicized content
    descriptors, section sub-titles, and epigraph attributions that leak
    into the raw downloaded text.
    """
    lines = text.split("\n")
    cleaned: list[str] = []

    for line in lines:
        stripped = line.strip()

        # Skip empty lines (will re-add spacing later)
        if not stripped:
            cleaned.append("")
            continue

        # Publication metadata: "Gallimard, 1946..." or volume title + Gallimard
        if re.match(r"^(Du côté de chez Swann|Le Temps retrouvé|Sodome et Gomorrhe|"
                     r"La Prisonnière|Albertine disparue|Le Côté de Guermantes|"
                     r"À l.ombre des jeunes filles en fleurs)$", stripped):
            continue
        if re.match(r"^Gallimard,\s*\d{4}", stripped):
            continue
        if re.match(r"^À la recherche du temps perdu \(\d{4}", stripped):
            continue

        # Part titles: "Première partie", "Deuxième partie", etc.
        if re.match(
            r"^(Première|Deuxième|Troisième|Quatrième)\s+partie\s*(:|$)",
            stripped, re.IGNORECASE,
        ):
            continue

        # Decorated part headers: *PREMIÈRE PARTIE*, *DEUXIÈME PARTIE*, etc.
        if re.match(
            r"^\*(PREMIÈRE|DEUXIÈME|TROISIÈME|QUATRIÈME)\s+PARTIE\*$",
            stripped,
        ):
            continue

        # Chapter identifiers: COMBRAY I, UN AMOUR DE SWANN, CHAPITRE PREMIER, etc.
        if re.match(r"^COMBRAY\s+[IVX]+$", stripped):
            continue
        if re.match(r"^UN AMOUR DE SWANN$", stripped):
            continue
        if re.match(r"^NOMS DE PAYS\s*:", stripped):
            continue
        if re.match(
            r"^CHAPITRE\s+(PREMIER|DEUXIÈME|TROISIÈME|QUATRIÈME|"
            r"CINQUIÈME|SIXIÈME|[IVX]+|\d+)\s*$",
            stripped, re.IGNORECASE,
        ):
            continue

        # Uppercase section headers (e.g. PREMIÈRE APPARITION DES HOMMES-FEMMES...)
        if re.match(r"^[A-ZÀ-Ÿ][A-ZÀ-Ÿ\s,\-\u2019'.…]+$", stripped):
            if len(stripped) > 10:
                continue

        # Italicized metadata headers: lines fully in *asterisks* that describe content
        # e.g. *Vie en commun avec Albertine*, *M. de Charlus dans le monde...*
        if re.match(r"^\*[^*]+\*$", stripped):
            continue

        # Epigraph quotes: lines starting with « and short quote fragments
        if re.match(r'^[«»\u00ab\u00bb]', stripped) and len(stripped) < 120:
            continue
        # Continuation of epigraph (line ending with »)
        if re.match(r"^.*[»\u00bb]\s*$", stripped) and len(stripped) < 120:
            # Only skip if near the start (before narrative)
            if not cleaned or all(not l.strip() for l in cleaned[-5:]):
                continue

        # Section sub-titles after chapter markers (short title-case lines
        # that appear right after a chapter header was removed):
        # "Le chagrin et l'oubli", "Tansonville", "Matinée chez la princesse..."
        # These are identified as short lines (< 80 chars) at the start of text,
        # before any substantial paragraph content.
        # We handle these in a second pass below.

        # Epigraph attributions: standalone author name lines like "Alfred de Vigny."
        if re.match(r"^[A-ZÀ-Ÿ][a-zà-ÿ]+(\s+de\s+)?[A-ZÀ-Ÿ][a-zà-ÿ]+\.\s*$", stripped):
            continue

        cleaned.append(line)

    text = "\n".join(cleaned)

    # Strip leading non-narrative lines at the start of text.
    # After line-by-line cleaning, some short title/subtitle/epigraph lines
    # may remain at the start before the actual narrative begins.
    text = text.strip()
    while text:
        first_line_end = text.find("\n")
        if first_line_end == -1:
            break
        first_line = text[:first_line_end].strip()
        if not first_line:
            text = text[first_line_end + 1:]
            continue
        # All-uppercase lines are headers, not narrative — remove regardless of length
        if first_line == first_line.upper() and len(first_line) > 10 and re.search(r"[A-ZÀ-Ÿ]", first_line):
            text = text[first_line_end + 1:]
            text = text.strip()
            continue
        # Epigraph quotes starting with « or ending with »
        if first_line[0] in ('«', '\u00ab') and len(first_line) < 120:
            text = text[first_line_end + 1:]
            text = text.strip()
            continue
        # Continuation/closing of epigraph
        if first_line.endswith(('»', '\u00bb', '»')) and len(first_line) < 120:
            text = text[first_line_end + 1:]
            text = text.strip()
            continue
        # Stop if the line looks like actual narrative (starts lowercase, or is long)
        if first_line[0].islower():
            break
        if len(first_line) > 80:
            break
        # Short title-like line at the start — likely a sub-title
        if len(first_line) < 80 and not first_line.endswith("."):
            text = text[first_line_end + 1:]
            text = text.strip()
            continue
        break

    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    return text


def fetch_page_content(title: str) -> str | None:
    """Fetch rendered page content via the parse API and convert to text."""
    params = {
        "action": "parse",
        "page": title,
        "prop": "text",
        "disablelimitreport": True,
        "disableeditsection": True,
        "disabletoc": True,
        "format": "json",
    }
    try:
        resp = requests.get(API_URL, params=params, headers=HEADERS, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        if "error" in data:
            print(f"    API error: {data['error'].get('info', 'unknown')}")
            return None

        html = data.get("parse", {}).get("text", {}).get("*", "")
        if not html:
            return None

        return html_to_text(html)
    except Exception as e:
        print(f"  Error fetching '{title}': {e}")
        return None


def download_volume(vol_info: dict) -> dict:
    """Download all chapters/sections for a volume."""
    root = vol_info["wikisource_root"]
    volume_num = vol_info["volume"]
    print(f"\n{'='*60}")
    print(f"Volume {volume_num}: {vol_info['title_fr']}")
    print(f"{'='*60}")

    chapters = []
    chapter_pages = vol_info.get("chapters", [])

    if not chapter_pages:
        # No subpages — fetch main page as single chapter
        print(f"  Fetching main page: {root}")
        content = fetch_page_content(root)
        time.sleep(2)
        if content and len(content) > 200:
            chapters.append({
                "chapter": vol_info["title_fr"],
                "wiki_title": root,
                "text": content,
                "char_count": len(content),
            })
            print(f"    -> {len(content):,} chars")
        else:
            print(f"    -> Not found or too short")
    else:
        print(f"  {len(chapter_pages)} chapters to fetch")
        for page_title in chapter_pages:
            chapter_name = page_title.replace(root + "/", "")
            print(f"  Fetching: {chapter_name} ...")
            content = fetch_page_content(page_title)
            time.sleep(2)  # Rate limiting

            if content:
                if len(content) > 200:
                    chapters.append({
                        "chapter": chapter_name,
                        "wiki_title": page_title,
                        "text": content,
                        "char_count": len(content),
                    })
                    print(f"    -> {len(content):,} chars")
                else:
                    print(f"    -> Skipped (too short: {len(content)} chars)")
            else:
                print(f"    -> Not found")

    result = {
        "volume": volume_num,
        "title_en": vol_info["title_en"],
        "title_fr": vol_info["title_fr"],
        "chapter_count": len(chapters),
        "total_chars": sum(ch["char_count"] for ch in chapters),
        "chapters": chapters,
    }

    return result


def main():
    print("Downloading Proust's French text from Wikisource")
    print("This may take several minutes due to rate limiting.\n")

    for vol_info in VOLUMES:
        result = download_volume(vol_info)

        # Save to file
        output_path = DATA_DIR / f"volume_{vol_info['volume']}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"\n  Saved to {output_path}")
        print(f"  {result['chapter_count']} chapters, {result['total_chars']:,} chars total")

    print("\n\nDownload complete!")
    print(f"Files saved to: {DATA_DIR}")


if __name__ == "__main__":
    main()
