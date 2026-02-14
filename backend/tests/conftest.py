"""
Shared pytest fixtures for ProustGPT backend tests.

All external services (Pinecone, Groq, Cohere) are mocked so tests
run without API keys or network access.
"""
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Mock external services BEFORE importing server (which imports retrieval.py
# at module level, which creates singleton clients)
# ---------------------------------------------------------------------------

def _mock_check_pinecone_connection():
    return {"connected": False, "error": "Mocked — no API key in CI"}


def _mock_query_rag(query: str):
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


def _mock_query_reflect(message: str):
    return f"Mocked reflection for: {message}"


def _mock_stream_rag_response(query: str):
    yield {"type": "token", "token": "Mocked "}
    yield {"type": "token", "token": "streaming "}
    yield {"type": "token", "token": "reply."}
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
    yield {"type": "done", "done": True}


def _mock_stream_reflect_response(message: str):
    yield {"type": "token", "token": "Mocked "}
    yield {"type": "token", "token": "reflection."}
    yield {"type": "done", "done": True}


def _mock_get_table_of_contents():
    return [
        {
            "volume": 1,
            "title": "Swann's Way",
            "chapters": [
                {"name": "Combray", "passage_count": 100}
            ],
        }
    ]


def _mock_get_chapter_passages(volume, chapter, offset, limit):
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
        patch("server.retrieve_passages", return_value=[]),
        patch("server.get_table_of_contents", side_effect=_mock_get_table_of_contents),
        patch("server.get_chapter_passages", side_effect=_mock_get_chapter_passages),
    ):
        from server import app
        with TestClient(app) as tc:
            yield tc
