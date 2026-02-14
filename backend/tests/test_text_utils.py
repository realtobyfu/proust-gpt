"""
Pure unit tests for text_utils.clean_passage_text.

No mocks needed — these test pure string transformations.
"""
import sys
import os

# Ensure backend/ is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from text_utils import clean_passage_text


def test_francoise_replacement():
    assert "Françoise" in clean_passage_text("Fran^oise said hello")


def test_francaise_replacement():
    assert "Française" in clean_passage_text("the Fran^aise style")


def test_francais_replacement():
    assert "Français" in clean_passage_text("the Fran^ais language")


def test_alencon_replacement():
    assert "Alençon" in clean_passage_text("the town of Alen^on")


def test_combray_line_break():
    assert "Combray" in clean_passage_text("Com-bray was a town")


def test_stray_caret_removal():
    result = clean_passage_text("^Contemplations of the past")
    assert result == "Contemplations of the past"


def test_whitespace_normalization():
    result = clean_passage_text("too   many    spaces")
    assert result == "too many spaces"


def test_empty_string():
    assert clean_passage_text("") == ""


def test_none_passthrough():
    assert clean_passage_text(None) is None


def test_no_changes_needed():
    text = "A perfectly normal sentence."
    assert clean_passage_text(text) == text


def test_multiple_replacements():
    text = "Fran^oise and the Fran^aise tradition in Alen^on"
    result = clean_passage_text(text)
    assert "Françoise" in result
    assert "Française" in result
    assert "Alençon" in result


def test_double_error_franuoise():
    assert "Françoise" in clean_passage_text("Fraru^oise was cooking")


def test_stray_c_artifact():
    assert "Françoise" in clean_passage_text("cFran^oise went out")
