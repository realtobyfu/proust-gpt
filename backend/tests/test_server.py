"""
Tests for ProustGPT FastAPI endpoints.

All external services are mocked via conftest.py fixtures.
"""
import asyncio
import json
from unittest.mock import patch


# =============================================================================
# Health check
# =============================================================================


def test_health_returns_200(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("healthy", "degraded")
    assert "pinecone" in data
    assert "llm_configured" in data


def test_health_shows_degraded_without_keys(client):
    resp = client.get("/health")
    data = resp.json()
    # With mocked (empty) keys, should be degraded
    assert data["status"] == "degraded"


# =============================================================================
# Non-streaming explore
# =============================================================================


def test_explore_returns_passages_and_reply(client):
    resp = client.post(
        "/api/explore_lost_time",
        json={"query": "madeleine memory"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "passages" in data
    assert "reply" in data
    assert len(data["passages"]) > 0
    assert "Mocked reply" in data["reply"]


def test_explore_empty_query_returns_empty(client):
    resp = client.post(
        "/api/explore_lost_time",
        json={"query": ""},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["passages"] == []


# =============================================================================
# Non-streaming reflect
# =============================================================================


def test_reflect_returns_reply(client):
    resp = client.post(
        "/api/reflect",
        json={"message": "I had a beautiful walk today."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "reply" in data
    assert "Mocked agent reflection" in data["reply"]


def test_reflect_empty_message(client):
    resp = client.post("/api/reflect", json={"message": ""})
    assert resp.status_code == 200
    data = resp.json()
    assert data["reply"] == "No message received."


# =============================================================================
# Streaming explore (SSE)
# =============================================================================


def test_explore_stream_returns_sse(client):
    resp = client.post(
        "/api/explore_lost_time/stream",
        json={"query": "madeleine memory"},
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]

    events = _parse_sse(resp.text)
    types = [e["type"] for e in events]
    assert types == ["sources", "token", "token", "token", "done"]
    assert "error" not in types


def test_explore_stream_empty_query(client):
    resp = client.post(
        "/api/explore_lost_time/stream",
        json={"query": ""},
    )
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    assert any(e.get("type") == "error" for e in events)


# =============================================================================
# Streaming reflect (SSE)
# =============================================================================


def test_reflect_stream_returns_sse(client):
    resp = client.post(
        "/api/reflect/stream",
        json={"message": "I had a good day"},
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]

    events = _parse_sse(resp.text)
    types = [e["type"] for e in events]
    assert types == ["status", "token", "token", "token", "done"]
    assert "error" not in types


def test_explore_stream_agent_returns_expected_order(client):
    with patch("server.needs_agent", return_value=True):
        resp = client.post(
            "/api/explore_lost_time/stream",
            json={"query": "compare Swann and Charlus"},
        )

    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    types = [e["type"] for e in events]
    assert types == ["status", "sources", "token", "token", "token", "done"]
    assert "error" not in types


def test_reflect_stream_empty_message(client):
    resp = client.post(
        "/api/reflect/stream",
        json={"message": ""},
    )
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    assert any(e.get("type") == "error" for e in events)


def test_reflect_stream_with_history(client):
    resp = client.post(
        "/api/reflect/stream",
        json={
            "message": "The smell of rain reminded me of my grandmother's garden.",
            "history": [
                {"role": "user", "content": "I had a beautiful walk today."},
                {"role": "assistant", "content": "What a lovely experience."},
            ],
        },
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]

    events = _parse_sse(resp.text)
    types = [e["type"] for e in events]
    assert "status" in types
    assert "token" in types
    assert "done" in types
    assert "error" not in types


def test_reflect_with_history_non_streaming(client):
    resp = client.post(
        "/api/reflect",
        json={
            "message": "The smell of rain reminded me of my grandmother's garden.",
            "history": [
                {"role": "user", "content": "I had a beautiful walk today."},
                {"role": "assistant", "content": "What a lovely experience."},
            ],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "reply" in data
    assert "agent reflection" in data["reply"]


# =============================================================================
# Read endpoints (no API keys needed, but corpus is mocked)
# =============================================================================


def test_read_toc(client):
    resp = client.get("/api/read/toc")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert data[0]["volume"] == 1


def test_read_chapter(client):
    resp = client.get("/api/read/chapter", params={"volume": 1, "chapter": "Combray"})
    assert resp.status_code == 200
    data = resp.json()
    assert "passages" in data


def test_read_chapter_not_found(client):
    resp = client.get("/api/read/chapter", params={"volume": 99, "chapter": "Nonexistent"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["error"] == "Chapter not found"


def test_async_sse_generator_stops_cleanly():
    from server import async_sse_generator

    def simple_stream():
        yield {"type": "token", "token": "Hello"}
        yield {"type": "sources", "passages": [{"book": "Swann's Way", "chapter": "Combray", "text": "Mocked"}]}
        yield {"type": "done", "done": True}

    async def collect() -> str:
        chunks = []
        async for chunk in async_sse_generator(simple_stream):
            chunks.append(chunk)
        return "".join(chunks)

    events = _parse_sse(asyncio.run(collect()))
    types = [e["type"] for e in events]
    assert types == ["token", "sources", "done"]
    assert "error" not in types


# =============================================================================
# Helpers
# =============================================================================


def _parse_sse(text: str) -> list[dict]:
    """Parse SSE text into a list of event dicts."""
    events = []
    for line in text.strip().split("\n\n"):
        for part in line.split("\n"):
            if part.startswith("data: "):
                try:
                    events.append(json.loads(part[6:]))
                except json.JSONDecodeError:
                    pass
    return events
