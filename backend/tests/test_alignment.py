#!/usr/bin/env python3
"""
Tests for the anchor-based bilingual alignment pipeline.

Unit tests (no API calls, no data files needed):
    pytest tests/test_alignment.py -k "not integration and not smoke"

Integration tests (requires --test output):
    python scripts/align_sentences.py --test
    pytest tests/test_alignment.py -k integration

Smoke tests (requires full output in parsed_clean_bilingual.json):
    python scripts/align_sentences.py
    pytest tests/test_alignment.py -k smoke

Usage:
    cd backend
    pytest tests/test_alignment.py -v
"""

import json
import sys
from pathlib import Path

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from scripts.align_sentences import (
    split_paragraphs,
    extract_anchors,
    lcs_anchor_pairs,
    sparsify_anchors,
    align_paragraphs_proportional,
    align_between_anchors,
    align_chapter,
    group_pairs_into_chunks,
    _merge_short_chunks,
    _is_section_marker,
    _filter_paragraphs,
    ANCHOR_NAMES,
)

BACKEND_DIR = Path(__file__).parent.parent
DATA_PATH = BACKEND_DIR / "parsed_clean_bilingual.json"


# ── Unit Tests ───────────────────────────────────────────────────────────────

class TestSplitParagraphs:
    """Test paragraph splitting and guillemet handling."""

    def test_basic_split(self):
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        paras = split_paragraphs(text)
        assert len(paras) == 3
        assert paras[0] == "First paragraph."
        assert paras[1] == "Second paragraph."
        assert paras[2] == "Third paragraph."

    def test_whitespace_normalization(self):
        text = "Some   text  with   spaces.\n\nAnother   paragraph."
        paras = split_paragraphs(text)
        assert paras[0] == "Some text with spaces."
        assert paras[1] == "Another paragraph."

    def test_empty_paragraphs_skipped(self):
        text = "First.\n\n\n\n\n\nSecond."
        paras = split_paragraphs(text)
        assert len(paras) == 2

    def test_orphaned_guillemets_merged(self):
        """Orphaned » or « should be merged into previous paragraph."""
        text = "Il dit quelque chose.\n\n»\n\nPuis il se tut."
        paras = split_paragraphs(text)
        assert len(paras) == 2
        assert "»" in paras[0]  # merged into previous
        assert paras[1] == "Puis il se tut."

    def test_empty_text(self):
        assert split_paragraphs("") == []
        assert split_paragraphs("   ") == []

    def test_single_paragraph(self):
        paras = split_paragraphs("Just one paragraph.")
        assert len(paras) == 1
        assert paras[0] == "Just one paragraph."


class TestSectionMarkers:
    """Test section marker detection and filtering."""

    def test_roman_numerals(self):
        assert _is_section_marker("II")
        assert _is_section_marker("IV")
        assert _is_section_marker("XII")

    def test_asterisks(self):
        assert _is_section_marker("* * *")

    def test_chapter_headers(self):
        assert _is_section_marker("CHAPTER I")
        assert _is_section_marker("CHAPITRE II")

    def test_narrative_not_marker(self):
        assert not _is_section_marker("The narrator went to bed early.")
        assert not _is_section_marker("Il me dit quelque chose.")

    def test_filter_paragraphs(self):
        paras = ["First paragraph.", "II", "Second paragraph.", "* * *", "Third."]
        filtered = _filter_paragraphs(paras)
        assert len(filtered) == 3
        assert filtered == ["First paragraph.", "Second paragraph.", "Third."]


class TestExtractAnchors:
    """Test proper noun anchor extraction."""

    def test_basic_extraction(self):
        text = "Swann came to visit us at Combray every summer."
        anchors = extract_anchors(text)
        assert len(anchors) == 2
        assert anchors[0][1] == "Swann"
        assert anchors[1][1] == "Combray"

    def test_positions_correct(self):
        text = "Hello Swann and Odette"
        anchors = extract_anchors(text)
        assert len(anchors) == 2
        assert text[anchors[0][0]:anchors[0][0] + len("Swann")] == "Swann"
        assert text[anchors[1][0]:anchors[1][0] + len("Odette")] == "Odette"

    def test_no_anchors(self):
        text = "The narrator went to bed early that night."
        anchors = extract_anchors(text)
        assert len(anchors) == 0

    def test_french_text(self):
        text = "Swann venait nous voir à Combray chaque été."
        anchors = extract_anchors(text)
        assert len(anchors) == 2
        assert anchors[0][1] == "Swann"
        assert anchors[1][1] == "Combray"

    def test_multiple_occurrences(self):
        text = "Swann said hello. Then Swann left."
        anchors = extract_anchors(text)
        assert len(anchors) == 2
        assert all(a[1] == "Swann" for a in anchors)

    def test_word_boundary(self):
        """Should not match partial words."""
        text = "The Swannery was beautiful."
        anchors = extract_anchors(text)
        # "Swannery" should not match "Swann" due to word boundary
        assert len(anchors) == 0

    def test_accented_names(self):
        text = "Françoise prepared the dinner at Méséglise."
        anchors = extract_anchors(text)
        names = [a[1] for a in anchors]
        assert "Françoise" in names
        assert "Méséglise" in names


class TestLCSAnchorPairs:
    """Test LCS matching of anchor sequences."""

    def test_identical_sequences(self):
        en = [(100, "Swann"), (500, "Odette"), (900, "Combray")]
        fr = [(120, "Swann"), (480, "Odette"), (880, "Combray")]
        pairs = lcs_anchor_pairs(en, fr, 1000, 1000)
        assert len(pairs) == 3

    def test_different_names_no_match(self):
        en = [(100, "Swann"), (500, "Odette")]
        fr = [(100, "Charlus"), (500, "Bloch")]
        pairs = lcs_anchor_pairs(en, fr, 1000, 1000)
        assert len(pairs) == 0

    def test_band_constraint(self):
        """Names far from the diagonal should not match."""
        en = [(10, "Swann")]   # position 1% in EN
        fr = [(900, "Swann")]  # position 90% in FR
        pairs = lcs_anchor_pairs(en, fr, 1000, 1000, band_pct=0.15)
        assert len(pairs) == 0  # too far from diagonal

    def test_band_allows_nearby(self):
        """Names near the diagonal should match."""
        en = [(100, "Swann")]  # position 10% in EN
        fr = [(150, "Swann")]  # position 15% in FR
        pairs = lcs_anchor_pairs(en, fr, 1000, 1000, band_pct=0.15)
        assert len(pairs) == 1

    def test_empty_inputs(self):
        assert lcs_anchor_pairs([], [], 0, 0) == []
        assert lcs_anchor_pairs([(0, "Swann")], [], 100, 0) == []

    def test_subsequence_matching(self):
        """LCS should find the longest common subsequence."""
        en = [(100, "Swann"), (300, "Odette"), (500, "Charlus"), (700, "Swann")]
        fr = [(100, "Odette"), (400, "Swann"), (600, "Charlus")]
        pairs = lcs_anchor_pairs(en, fr, 1000, 1000, band_pct=0.30)
        # Should match Odette-Odette, Charlus-Charlus at minimum
        assert len(pairs) >= 2


class TestSparsifyAnchors:
    """Test anchor sparsification."""

    def test_basic_sparsify(self):
        pairs = [(0, 0), (100, 100), (3000, 3000), (3100, 3100), (6000, 6000)]
        sparse = sparsify_anchors(pairs, min_spacing=2000)
        assert len(sparse) == 3
        assert sparse == [(0, 0), (3000, 3000), (6000, 6000)]

    def test_all_close(self):
        pairs = [(0, 0), (100, 100), (200, 200)]
        sparse = sparsify_anchors(pairs, min_spacing=2000)
        assert len(sparse) == 1
        assert sparse == [(0, 0)]

    def test_empty(self):
        assert sparsify_anchors([], min_spacing=2000) == []

    def test_single_pair(self):
        pairs = [(500, 500)]
        assert sparsify_anchors(pairs) == [(500, 500)]


class TestProportionalAlignment:
    """Test FR-primary proportional paragraph alignment."""

    def test_equal_paragraphs(self):
        en = ["First en paragraph.", "Second en paragraph.", "Third en paragraph."]
        fr = ["Premier paragraphe.", "Deuxième paragraphe.", "Troisième paragraphe."]
        pairs = align_paragraphs_proportional(en, fr)
        # One pair per FR paragraph
        assert len(pairs) == 3
        assert "First" in pairs[0][0]
        assert "Premier" in pairs[0][1]

    def test_more_en_than_fr(self):
        """EN paragraphs get grouped to match FR (the original)."""
        en = ["A.", "B.", "C.", "D.", "E.", "F."]
        fr = ["X.", "Y.", "Z."]
        pairs = align_paragraphs_proportional(en, fr)
        # One pair per FR paragraph — EN gets grouped
        assert len(pairs) == 3
        all_en = " ".join(p[0] for p in pairs)
        for letter in "ABCDEF":
            assert f"{letter}." in all_en
        # Each FR paragraph preserved intact
        assert pairs[0][1] == "X."
        assert pairs[1][1] == "Y."
        assert pairs[2][1] == "Z."

    def test_more_fr_than_en(self):
        """Even with more FR paragraphs, each FR paragraph gets its own pair."""
        en = ["A.", "B."]
        fr = ["X.", "Y.", "Z.", "W."]
        pairs = align_paragraphs_proportional(en, fr)
        # One pair per FR paragraph — FR structure preserved
        assert len(pairs) == 4
        all_en = " ".join(p[0] for p in pairs)
        for letter in "AB":
            assert f"{letter}." in all_en
        # Each FR paragraph preserved intact
        for i, letter in enumerate("XYZW"):
            assert pairs[i][1] == f"{letter}."

    def test_empty_en(self):
        pairs = align_paragraphs_proportional([], ["X.", "Y."])
        assert len(pairs) == 2
        assert all(p[0] == "" for p in pairs)

    def test_empty_fr(self):
        pairs = align_paragraphs_proportional(["A.", "B."], [])
        assert len(pairs) == 1  # All EN grouped into one
        assert pairs[0][1] == ""

    def test_both_empty(self):
        assert align_paragraphs_proportional([], []) == []

    def test_single_each(self):
        pairs = align_paragraphs_proportional(["Hello."], ["Bonjour."])
        assert len(pairs) == 1
        assert pairs[0] == ("Hello.", "Bonjour.")

    def test_fr_paragraphs_never_split(self):
        """FR paragraphs should never be split or combined."""
        en = ["Short."]
        fr = ["First FR paragraph.", "Second FR paragraph.", "Third FR paragraph."]
        pairs = align_paragraphs_proportional(en, fr)
        assert len(pairs) == 3  # One per FR paragraph
        fr_texts = [p[1] for p in pairs]
        assert "First FR paragraph." in fr_texts
        assert "Second FR paragraph." in fr_texts
        assert "Third FR paragraph." in fr_texts


class TestAlignChapter:
    """Test the full anchor-based alignment pipeline."""

    def test_simple_chapter(self):
        en_text = ("Swann came to visit us at Combray.\n\n"
                   "Françoise prepared dinner.\n\n"
                   "We walked by Swann's way.")
        fr_text = ("Swann venait nous voir à Combray.\n\n"
                   "Françoise préparait le dîner.\n\n"
                   "Nous marchions du côté de chez Swann.")
        pairs = align_chapter(en_text, fr_text)
        assert len(pairs) >= 1
        # All EN text should be present
        all_en = " ".join(p[0] for p in pairs)
        assert "Swann" in all_en
        assert "Françoise" in all_en

    def test_no_anchors_still_works(self):
        """Even without anchors, proportional alignment should work."""
        en_text = "The narrator went to bed early.\n\nHe could not sleep."
        fr_text = "Le narrateur se coucha de bonne heure.\n\nIl ne pouvait dormir."
        pairs = align_chapter(en_text, fr_text)
        assert len(pairs) >= 1


class TestGroupPairsIntoChunks:
    """Test chunk grouping from aligned pairs."""

    def test_small_pairs_merged(self):
        """Short pairs should be merged into larger chunks."""
        pairs = [("Short A.", "Court A."), ("Short B.", "Court B.")]
        chunks = group_pairs_into_chunks(pairs)
        assert len(chunks) == 1  # Both merged into one chunk

    def test_large_fr_paras_separate_chunks(self):
        """Large FR paragraphs should create separate chunks."""
        long_en = "x" * 800
        long_fr = "y" * 800
        pairs = [(long_en, long_fr), (long_en, long_fr)]
        chunks = group_pairs_into_chunks(pairs)
        assert len(chunks) == 2

    def test_empty_pairs(self):
        assert group_pairs_into_chunks([]) == []

    def test_all_text_preserved(self):
        """All input text should appear in output chunks."""
        pairs = [(f"EN paragraph {i}." * 20, f"FR paragraphe {i}." * 20)
                 for i in range(10)]
        chunks = group_pairs_into_chunks(pairs)
        all_en = " ".join(c[0] for c in chunks)
        for i in range(10):
            assert f"EN paragraph {i}" in all_en


class TestMergeShortChunks:
    """Test short chunk merging."""

    def test_short_merged_into_previous(self):
        chunks = [
            ("This is a long enough chunk." * 5, "Ceci est assez long." * 5),
            ("Short.", "Court."),
        ]
        merged = _merge_short_chunks(chunks)
        assert len(merged) == 1

    def test_long_chunks_kept(self):
        chunks = [
            ("This is a long chunk." * 10, "Ceci est long." * 10),
            ("Another long chunk." * 10, "Un autre long." * 10),
        ]
        merged = _merge_short_chunks(chunks)
        assert len(merged) == 2

    def test_single_chunk(self):
        chunks = [("Hello.", "Bonjour.")]
        assert _merge_short_chunks(chunks) == chunks

    def test_empty(self):
        assert _merge_short_chunks([]) == []


# ── Integration Tests (require --test output) ───────────────────────────────

class TestIntegration:
    """Tests that require running align_sentences.py --test first."""

    @pytest.fixture
    def passages(self):
        if not DATA_PATH.exists():
            pytest.skip("parsed_clean_bilingual.json not found — run align_sentences.py first")
        with open(DATA_PATH, encoding="utf-8") as f:
            data = json.load(f)
        # Filter to Vol 1 Overture
        return [p for p in data if p.get("volume") == 1
                and p.get("chapter") == "Overture"]

    @pytest.mark.integration
    def test_vol1_overture_no_empty_fr(self, passages):
        """All Overture passages should have French text."""
        if not passages:
            pytest.skip("No Vol 1 Overture passages found")
        empty = [p for p in passages if not p.get("text_fr")]
        assert len(empty) == 0, f"{len(empty)} passages have empty text_fr"

    @pytest.mark.integration
    def test_vol1_overture_length_ratios(self, passages):
        """Less than 10% of passages should have >3x EN/FR length ratio."""
        if not passages:
            pytest.skip("No Vol 1 Overture passages found")
        bad = 0
        total = 0
        for p in passages:
            en_len = len(p.get("text", ""))
            fr_len = len(p.get("text_fr", ""))
            if en_len > 0 and fr_len > 0:
                total += 1
                ratio = max(en_len, fr_len) / min(en_len, fr_len)
                if ratio > 3.0:
                    bad += 1
        pct = bad / total * 100 if total else 0
        assert pct < 10, f"{bad}/{total} ({pct:.1f}%) have >3x ratio"

    @pytest.mark.integration
    def test_vol1_overture_opening(self, passages):
        """First passage should start with 'For a long time' / 'Longtemps'."""
        if not passages:
            pytest.skip("No Vol 1 Overture passages found")
        first = passages[0]
        assert "long time" in first["text"][:100].lower() or \
               "bed early" in first["text"][:100].lower(), \
               f"Unexpected EN opening: {first['text'][:100]}"
        assert "longtemps" in first["text_fr"][:100].lower(), \
               f"Unexpected FR opening: {first['text_fr'][:100]}"

    @pytest.mark.integration
    def test_vol1_overture_chunk_count(self, passages):
        """Overture should produce a reasonable number of chunks."""
        if not passages:
            pytest.skip("No Vol 1 Overture passages found")
        # Overture is ~50-80 pages, should produce 80-300 chunks
        assert 50 < len(passages) < 500, \
               f"Unexpected chunk count: {len(passages)}"


# ── Smoke Tests (require full output) ────────────────────────────────────────

class TestSmoke:
    """Tests that require the full corpus in parsed_clean_bilingual.json."""

    @pytest.fixture
    def all_passages(self):
        if not DATA_PATH.exists():
            pytest.skip("parsed_clean_bilingual.json not found")
        with open(DATA_PATH, encoding="utf-8") as f:
            return json.load(f)

    @pytest.mark.smoke
    def test_no_empty_french(self, all_passages):
        """Very few passages should have empty French text."""
        empty = [p for p in all_passages if not p.get("text_fr")]
        pct = len(empty) / len(all_passages) * 100
        assert pct < 1.0, f"{len(empty)} passages ({pct:.1f}%) have empty text_fr"

    @pytest.mark.smoke
    def test_length_ratios(self, all_passages):
        """Less than 5% of passages should have >3x length ratio."""
        bad = 0
        total = 0
        for p in all_passages:
            en_len = len(p.get("text", ""))
            fr_len = len(p.get("text_fr", ""))
            if en_len > 0 and fr_len > 0:
                total += 1
                ratio = max(en_len, fr_len) / min(en_len, fr_len)
                if ratio > 3.0:
                    bad += 1
        pct = bad / total * 100 if total else 0
        assert pct < 5.0, f"{bad}/{total} ({pct:.1f}%) have >3x ratio"

    @pytest.mark.smoke
    def test_chapter_coverage(self, all_passages):
        """Every volume should have passages."""
        volumes = set(p.get("volume") for p in all_passages)
        for vol in range(1, 8):
            assert vol in volumes, f"Volume {vol} has no passages"

    @pytest.mark.smoke
    def test_monotonic_order(self, all_passages):
        """Index should increase monotonically within each chapter."""
        from collections import defaultdict
        by_chapter = defaultdict(list)
        for p in all_passages:
            key = (p.get("volume"), p.get("chapter"))
            by_chapter[key].append(p.get("index"))

        for key, indices in by_chapter.items():
            assert indices == sorted(indices), \
                f"Non-monotonic indices in {key}: {indices[:10]}"

    @pytest.mark.smoke
    def test_vol3_has_french(self, all_passages):
        """Volume 3 should have French text (was previously zero)."""
        vol3 = [p for p in all_passages if p.get("volume") == 3]
        if not vol3:
            pytest.fail("Volume 3 has no passages at all")
        has_fr = sum(1 for p in vol3 if p.get("text_fr"))
        pct = has_fr / len(vol3) * 100
        assert pct > 90, f"Vol 3: only {has_fr}/{len(vol3)} ({pct:.1f}%) have FR"

    @pytest.mark.smoke
    def test_vol3_has_chapter_names(self, all_passages):
        """Vol 3 should use FR chapter names, not 'Full Volume'."""
        vol3 = [p for p in all_passages if p.get("volume") == 3]
        chapters = set(p.get("chapter") for p in vol3)
        assert "Full Volume" not in chapters, \
            "Vol 3 should use FR chapter names, not 'Full Volume'"
        # Should have at least 2 distinct chapter names
        assert len(chapters) >= 2, f"Vol 3 has only {len(chapters)} chapters: {chapters}"

    @pytest.mark.smoke
    def test_total_passage_count(self, all_passages):
        """Should have a reasonable total passage count."""
        # Paragraph-preserving approach produces ~4000-8000 passages
        # (fewer but larger than sentence-level splitting)
        assert 3000 < len(all_passages) < 25000, \
               f"Unexpected passage count: {len(all_passages)}"
