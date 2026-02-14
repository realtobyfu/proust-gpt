"""
Shared text cleaning utilities for ProustGPT.

Fixes OCR artifacts from the archive.org source text where the `^` character
was used as a cedilla substitute (ç).
"""

import re

# Ordered replacements: most specific first to avoid partial matches.
# The ^ in the source is a stand-in for ç (cedilla).
_REPLACEMENTS = [
    # OCR double-error
    ("Fraru^oise", "Françoise"),
    # Stray leading 'c' OCR artifact
    ("cFran^oise", "Françoise"),
    # Hyphenated line-break artifact
    ("Fran-^oise", "Françoise"),
    # Main patterns (longer before shorter to avoid partial replacement)
    ("Fran^oise", "Françoise"),
    ("Fran^aise", "Française"),
    ("Fran^ais", "Français"),
    ("Alen^on", "Alençon"),
    ("Ganan^ay", "Ganançay"),
    # Line-break artifact
    ("Com-bray", "Combray"),
]

# Stray ^ prefixes (^word → word)
_STRAY_CARET_RE = re.compile(r"\^(\w)")


def clean_passage_text(text: str) -> str:
    """
    Apply OCR artifact replacements, strip, and normalize whitespace.

    Args:
        text: Raw passage text from parsed.json.

    Returns:
        Cleaned text with proper diacritics and normalized whitespace.
    """
    if not text:
        return text

    for old, new in _REPLACEMENTS:
        text = text.replace(old, new)

    # Remove stray ^ prefixes (e.g. ^Contemplations → Contemplations)
    text = _STRAY_CARET_RE.sub(r"\1", text)

    # Collapse multiple spaces / normalize whitespace
    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()
