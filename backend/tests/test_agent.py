"""
Tests for the LangGraph agent layer (Workstream J1/J2).

These run without API keys: the router and passage-accumulation logic are pure,
and the streaming generator is exercised against a *fake* agent that mimics
LangGraph's ``stream_mode=["updates", "messages"]`` output. This covers the
correctness fixes A1 (concurrency), A2 (adjacency grounding), A3 (citation
integrity), A4 (graceful degrade) and A8 (tool-call leak suppression).
"""
import threading

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langgraph.errors import GraphRecursionError

import agent as A


# ── J1.1 Router accuracy gold set ─────────────────────────────────────────────

# (query, should_route_to_agent). Includes French comparative queries (C3).
ROUTER_GOLD = [
    # Fast path — simple lookups
    ("what is a madeleine?", False),
    ("Tell me about Combray", False),
    ("Describe the narrator's bedroom", False),
    ("Who is Odette?", False),
    ("the taste of the tea", False),
    ("qu'est-ce qu'une madeleine ?", False),
    ("Parlez-moi de Combray", False),
    # Agent path — comparative / multi-hop / evolution
    ("compare Swann and Charlus", True),
    ("comparison of jealousy in Swann and the narrator", True),
    ("how does Albertine change over time", True),
    ("trace the arc of the narrator's love", True),
    ("the relationship between Swann and Odette", True),
    ("what happens next after the goodnight kiss", True),
    ("which volume treats jealousy more deeply", True),
    ("how does Swann's jealousy evolve", True),
    # French agent-path
    ("comparez Swann et Charlus", True),
    ("comparaison entre Swann et Odette", True),
    ("quel volume traite le plus de la jalousie", True),
    ("la relation entre Swann et Odette", True),
    ("comment la jalousie évolue-t-elle", True),
]


def test_router_accuracy_meets_threshold():
    correct = sum(1 for q, expected in ROUTER_GOLD if A.needs_agent(q) == expected)
    accuracy = correct / len(ROUTER_GOLD)
    assert accuracy >= 0.9, f"Router accuracy {accuracy:.0%} below threshold"


def test_route_query_returns_rule():
    chose, rule = A.route_query("compare Swann and Charlus")
    assert chose is True and rule == "complex_pattern"
    chose, rule = A.route_query("what is a madeleine?")
    assert chose is False and rule == "fast_default"


def test_router_does_not_force_agent_on_long_history():
    """C2: a simple turn-3 query routes fast even with prior history."""
    history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
        {"role": "user", "content": "tell me more"},
        {"role": "assistant", "content": "sure"},
    ]
    assert A.needs_agent("what is a madeleine?", history) is False


def test_router_multi_question_routes_to_agent():
    assert A.needs_agent("Who is Swann? How does he change?") is True


# ── J2 Passage accumulator (A1/A2/A3) ─────────────────────────────────────────

def test_accumulator_dedupes_and_numbers_monotonically():
    acc = A._PassageAccumulator()
    b1 = acc.add([{"index": 5, "text": "a"}, {"index": 9, "text": "b"}])
    assert [p["citation_index"] for p in b1] == [1, 2]
    # index 9 already seen -> reuse cite 2; index 12 -> new cite 3
    b2 = acc.add([{"index": 9, "text": "b"}, {"index": 12, "text": "c"}])
    assert [p["citation_index"] for p in b2] == [2, 3]
    assert len(acc.passages) == 3


def test_render_batch_exposes_global_index_for_adjacency():
    """A2: the model must see the corpus #index to call get_adjacent_passages."""
    acc = A._PassageAccumulator()
    batch = acc.add([{"index": 812, "text": "scene", "book": "B", "chapter": "C"}])
    rendered = A._render_batch(batch)
    assert "passage #812" in rendered
    assert "[1]" in rendered


# ── Fake agent harness for streaming tests ────────────────────────────────────

class _FakeAgent:
    """Mimics agent.stream(stream_mode=["updates","messages"])."""

    def __init__(self, acc, *, tool_batch=None, tokens=None, raise_recursion=False):
        self.acc = acc
        self.tool_batch = tool_batch or []
        self.tokens = tokens or []
        self.raise_recursion = raise_recursion

    def stream(self, inp, config=None, stream_mode=None):
        if self.tool_batch:
            tc = {"name": "search_passages", "args": {"query": "x"}, "id": "1"}
            yield ("updates", {"agent": {"messages": [AIMessage(content="", tool_calls=[tc])]}})
            self.acc.add(self.tool_batch)  # simulate the tool populating sources
        if self.raise_recursion:
            raise GraphRecursionError("recursion limit")
        for tok in self.tokens:
            yield ("messages", (AIMessageChunk(content=tok), {"langgraph_node": "agent"}))


def _run(agent, acc, lang="en"):
    return list(
        A._stream_agent(agent, [HumanMessage(content="q")], acc,
                        preview=True, intro="Thinking...", lang=lang)
    )


def test_stream_event_order_and_sources_before_tokens():
    acc = A._PassageAccumulator()
    fa = _FakeAgent(
        acc,
        tool_batch=[{"index": 5, "text": "t", "book": "B", "chapter": "C"}],
        tokens=["Answer ", "here [1]."],
    )
    events = _run(fa, acc)
    types = [e["type"] for e in events]
    assert types[0] == "status"
    assert "sources" in types and "token" in types
    assert types.index("sources") < types.index("token")  # sources first
    assert types[-1] == "done"
    assert "error" not in types


def test_citation_integrity_every_marker_has_a_source():
    """A3: each [n] in the reply maps to an emitted source n."""
    acc = A._PassageAccumulator()
    fa = _FakeAgent(
        acc,
        tool_batch=[
            {"index": 5, "text": "a", "book": "B", "chapter": "C"},
            {"index": 9, "text": "b", "book": "B", "chapter": "C"},
        ],
        tokens=["Swann [1] and Odette [2]."],
    )
    events = _run(fa, acc)
    reply = "".join(e["token"] for e in events if e["type"] == "token")
    source_cites = {e["passages"][0]["citation_index"] for e in events if e["type"] == "sources"}
    import re
    used = {int(n) for n in re.findall(r"\[(\d+)\]", reply)}
    assert used <= source_cites, f"orphan citations {used - source_cites}"


def test_preview_truncation_on_sources():
    acc = A._PassageAccumulator()
    long_text = "word " * 200  # >200 chars
    fa = _FakeAgent(acc, tool_batch=[{"index": 1, "text": long_text, "book": "B", "chapter": "C"}],
                    tokens=["ok [1]"])
    events = _run(fa, acc)
    src = next(e for e in events if e["type"] == "sources")
    assert len(src["passages"][0]["text"]) <= 205  # 200 + ellipsis


def test_graceful_degrade_on_recursion_limit(monkeypatch):
    """A4: recursion limit -> answer from gathered evidence, no error event."""
    class _FakeLLM:
        def stream(self, prompt):
            for t in ["From ", "evidence [1]."]:
                yield AIMessageChunk(content=t)

    monkeypatch.setattr(A, "get_llm", lambda: _FakeLLM())
    acc = A._PassageAccumulator()
    fa = _FakeAgent(acc, tool_batch=[{"index": 3, "text": "ev", "book": "B", "chapter": "C"}],
                    raise_recursion=True)
    events = _run(fa, acc)
    types = [e["type"] for e in events]
    reply = "".join(e["token"] for e in events if e["type"] == "token")
    assert "error" not in types
    assert types[-1] == "done"
    assert "sources" in types
    assert "evidence" in reply


def test_tool_call_leak_is_suppressed(monkeypatch):
    """A8: tool-call JSON leaking as content is not streamed to the user."""
    class _FakeLLM:
        def stream(self, prompt):
            yield AIMessageChunk(content="fallback answer")

    monkeypatch.setattr(A, "get_llm", lambda: _FakeLLM())
    acc = A._PassageAccumulator()
    fa = _FakeAgent(
        acc,
        tool_batch=[{"index": 1, "text": "x", "book": "B", "chapter": "C"}],
        tokens=['{"name": "search_passages"', ', "arguments": {}}'],
    )
    events = _run(fa, acc)
    streamed = "".join(e["token"] for e in events if e["type"] == "token")
    assert '"name"' not in streamed  # raw tool-call JSON never reaches the user


def test_two_interleaved_streams_do_not_leak_passages():
    """A1 regression: concurrent requests must not share passage state."""
    results = {}

    def worker(name, index, text):
        acc = A._PassageAccumulator()
        fa = _FakeAgent(acc, tool_batch=[{"index": index, "text": text, "book": "B", "chapter": "C"}],
                        tokens=[f"answer {name} [1]"])
        events = _run(fa, acc)
        srcs = [e["passages"][0] for e in events if e["type"] == "sources"]
        results[name] = [s["index"] for s in srcs]

    t1 = threading.Thread(target=worker, args=("A", 100, "alpha"))
    t2 = threading.Thread(target=worker, args=("B", 200, "beta"))
    t1.start(); t2.start(); t1.join(); t2.join()

    # Each stream sees ONLY its own passage — no cross-request contamination.
    assert results["A"] == [100]
    assert results["B"] == [200]
