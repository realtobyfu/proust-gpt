"""
Shared pytest fixtures for ProustGPT backend tests.

All external services (Pinecone, Groq, Cohere) are mocked so tests
run without API keys or network access.
"""
import json
import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Disable per-IP rate limiting during tests (the suite fires many chat requests
# from a single client IP, which would otherwise trip the limit — B1).
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")


# ---------------------------------------------------------------------------
# Mock external services BEFORE importing server (which imports retrieval.py
# at module level, which creates singleton clients)
# ---------------------------------------------------------------------------

def _mock_check_pinecone_connection():
    return {"connected": False, "error": "Mocked — no API key in CI"}


def _mock_query_rag(query: str, lang: str = "en", history=None):
    return {
        "reply": f"Mocked reply for: {query}",
        "passages": [
            {
                "book": "Swann's Way",
                "chapter": "Combray",
                "text": "Mocked passage text about memory and madeleines.",
                "volume": 1,
                "index": 42,
            }
        ],
    }


def _mock_query_reflect(message: str, lang: str = "en"):
    return f"Mocked reflection for: {message}"


def _mock_stream_rag_response(query: str, lang: str = "en", history=None):
    yield {
        "type": "sources",
        "passages": [
            {
                "book": "Swann's Way",
                "chapter": "Combray",
                "text": "Mocked passage.",
                "volume": 1,
                "index": 1,
            }
        ],
    }
    yield {"type": "token", "token": "Mocked "}
    yield {"type": "token", "token": "streaming "}
    yield {"type": "token", "token": "reply."}
    yield {"type": "done", "done": True}


def _mock_stream_reflect_response(message: str, lang: str = "en"):
    yield {"type": "token", "token": "Mocked "}
    yield {"type": "token", "token": "reflection."}
    yield {"type": "done", "done": True}


def _mock_stream_agent_response(query: str, history=None, lang: str = "en"):
    yield {"type": "status", "status": "Thinking..."}
    yield {
        "type": "sources",
        "passages": [
            {
                "book": "Swann's Way",
                "chapter": "Combray",
                "text": "Mocked passage.",
                "volume": 1,
                "index": 1,
            }
        ],
    }
    yield {"type": "token", "token": "Mocked "}
    yield {"type": "token", "token": "agent "}
    yield {"type": "token", "token": "reply."}
    yield {"type": "done", "done": True}


def _mock_query_agent(query: str, history=None, lang: str = "en"):
    return {
        "reply": f"Mocked agent reply for: {query}",
        "passages": [
            {
                "book": "Swann's Way",
                "chapter": "Combray",
                "text": "Mocked passage text about memory and madeleines.",
                "volume": 1,
                "index": 42,
            }
        ],
    }


def _mock_needs_agent(query: str, history=None):
    return False


def _mock_route_query(query: str, history=None):
    return (False, "fast_default")


def _mock_stream_reflect_agent_response(message: str, history=None, lang="en"):
    yield {"type": "status", "status": "Reflecting..."}
    yield {"type": "token", "token": "Mocked "}
    yield {"type": "token", "token": "agent "}
    yield {"type": "token", "token": "reflection."}
    yield {"type": "done", "done": True}


def _mock_query_reflect_agent(message: str, history=None, lang="en"):
    return {
        "reply": f"Mocked agent reflection for: {message}",
        "passages": [],
    }


def _mock_get_table_of_contents(lang: str = "en"):
    return [
        {
            "volume": 1,
            "title": "Swann's Way",
            "chapters": [
                {"name": "Combray", "passage_count": 100}
            ],
        }
    ]


def _mock_get_chapter_passages(volume, chapter, offset, limit, lang: str = "en"):
    if volume == 1 and chapter == "Combray":
        return {
            "passages": [{"text": "Mock passage", "index": offset}],
            "total": 100,
            "offset": offset,
            "limit": limit,
        }
    return None


@pytest.fixture()
def client():
    """
    Create a FastAPI TestClient with all external services mocked.
    """
    with (
        patch("server.check_pinecone_connection", side_effect=_mock_check_pinecone_connection),
        patch("server.query_rag", side_effect=_mock_query_rag),
        patch("server.query_reflect", side_effect=_mock_query_reflect),
        patch("server.stream_rag_response", side_effect=_mock_stream_rag_response),
        patch("server.stream_reflect_response", side_effect=_mock_stream_reflect_response),
        patch("server.stream_agent_response", side_effect=_mock_stream_agent_response),
        patch("server.query_agent", side_effect=_mock_query_agent),
        patch("server.needs_agent", side_effect=_mock_needs_agent),
        patch("server.route_query", side_effect=_mock_route_query),
        patch("server.stream_reflect_agent_response", side_effect=_mock_stream_reflect_agent_response),
        patch("server.query_reflect_agent", side_effect=_mock_query_reflect_agent),
        patch("server.retrieve_passages", return_value=[]),
        patch("server.get_table_of_contents", side_effect=_mock_get_table_of_contents),
        patch("server.get_chapter_passages", side_effect=_mock_get_chapter_passages),
    ):
        from server import app
        with TestClient(app) as tc:
            yield tc
