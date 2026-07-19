"""
Unit tests for pure retrieval/history helpers (Workstream J2).

No API keys required — these functions are deterministic.
"""
from langchain_core.documents import Document

import retrieval as R


# ── Repetition detection ──────────────────────────────────────────────────────

def test_detect_repetition_flags_loops():
    # A periodic string so the 60-char detection window recurs >= threshold times.
    looped = "abcdefghij" * 30
    assert R._detect_repetition(looped) is True


def test_detect_repetition_ignores_normal_text():
    normal = "Proust writes with long, winding sentences that rarely repeat themselves verbatim."
    assert R._detect_repetition(normal) is False


# ── Sentence-boundary detection (context stitching) ───────────────────────────

def test_starts_mid_sentence():
    assert R._starts_mid_sentence("and then he walked on") is True
    assert R._starts_mid_sentence("...continuing the thought") is True
    assert R._starts_mid_sentence("The morning was clear.") is False


def test_ends_mid_sentence():
    assert R._ends_mid_sentence("he walked on and") is True
    assert R._ends_mid_sentence("A complete sentence.") is False
    assert R._ends_mid_sentence("truncated here...") is True


# ── History helpers (C1/C4) ───────────────────────────────────────────────────

def test_strip_citation_markers():
    assert R.strip_citation_markers("He suffers [1] deeply [2].") == "He suffers deeply."


def test_cap_history_limits_turns_and_strips_citations():
    history = []
    for i in range(30):
        history.append({"role": "user", "content": f"q{i}"})
        history.append({"role": "assistant", "content": f"a{i} [1]"})
    capped = R.cap_history(history, max_turns=3)
    assert len(capped) <= 6  # 3 turns * 2 messages
    # citation markers stripped from assistant turns
    assert all("[1]" not in m["content"] for m in capped if m["role"] == "assistant")


def test_cap_history_empty():
    assert R.cap_history(None) == []
    assert R.cap_history([]) == []


def test_cap_history_truncates_long_messages():
    huge = "x" * (R.config.MAX_QUERY_CHARS + 500)
    capped = R.cap_history([{"role": "user", "content": huge}])
    assert len(capped[0]["content"]) <= R.config.MAX_QUERY_CHARS


# ── SSE preview truncation (A6) ───────────────────────────────────────────────

def test_preview_passage_truncates_long_text():
    p = {"text": "a" * 500, "text_fr": "b" * 500, "index": 1}
    preview = R._preview_passage(p)
    assert len(preview["text"]) <= R.SSE_TEXT_PREVIEW + 1  # +ellipsis
    assert preview["_truncated"] is True
    # original is untouched
    assert len(p["text"]) == 500


def test_preview_passage_keeps_short_text():
    p = {"text": "short", "index": 1}
    assert R._preview_passage(p)["text"] == "short"


# ── Passage formatting ────────────────────────────────────────────────────────

def test_format_passages_assigns_citation_index():
    docs = [
        Document(page_content="one", metadata={"index": 5, "book": "B", "chapter": "C"}),
        Document(page_content="two", metadata={"index": 9, "book": "B", "chapter": "C"}),
    ]
    passages = R._format_passages(docs)
    assert [p["citation_index"] for p in passages] == [1, 2]
    assert passages[0]["index"] == 5


# ── TTL/LRU cache (E1) ────────────────────────────────────────────────────────

def test_ttl_cache_hit_and_miss():
    cache = R._TTLCache(maxsize=4, ttl=100)
    assert cache.get("k") is None
    cache.set("k", "v")
    assert cache.get("k") == "v"
    assert cache.hits == 1 and cache.misses == 1


def test_ttl_cache_evicts_lru():
    cache = R._TTLCache(maxsize=2, ttl=100)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.get("a")            # touch 'a' so 'b' is now least-recently-used
    cache.set("c", 3)        # exceeds maxsize -> evict 'b'
    assert cache.get("a") == 1
    assert cache.get("c") == 3
    assert cache.get("b") is None


def test_ttl_cache_expires():
    cache = R._TTLCache(maxsize=4, ttl=0)  # ttl=0 -> immediately stale
    cache.set("k", "v")
    assert cache.get("k") is None
