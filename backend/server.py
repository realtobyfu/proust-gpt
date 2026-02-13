"""
ProustGPT FastAPI Backend

Provides both streaming (SSE) and non-streaming endpoints for:
- RAG-based passage retrieval from Proust's "In Search of Lost Time"
- Proustian-style reflection conversations
"""
import asyncio
import json
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import config
from retrieval import (
    query_rag,
    query_reflect,
    stream_rag_response,
    stream_reflect_response,
    check_pinecone_connection,
    retrieve_passages,
)


# =============================================================================
# Pydantic request/response models
# =============================================================================


class QueryRequest(BaseModel):
    query: Optional[str] = None
    message: Optional[str] = None


class PassageItem(BaseModel):
    book: str
    chapter: str
    text: str
    volume: Optional[int] = None
    index: Optional[int] = None


class ExploreResponse(BaseModel):
    passages: list[PassageItem] = []
    reply: str = ""
    error: Optional[str] = None


class ReflectResponse(BaseModel):
    reply: str


class HealthResponse(BaseModel):
    status: str
    pinecone: dict
    llm_configured: bool
    config_valid: bool
    missing_config: list[str]


# =============================================================================
# App setup
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate configuration on startup."""
    missing = config.validate()
    if missing:
        print(f"WARNING: Missing required configuration: {missing}")
        print("Some features may not work. See .env.example for setup instructions.")
    yield


app = FastAPI(title="ProustGPT", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# SSE helpers
# =============================================================================


def sse_format(data: dict) -> str:
    """Format data as SSE event."""
    return f"data: {json.dumps(data)}\n\n"


async def async_sse_generator(sync_gen_func, *args) -> AsyncGenerator[str, None]:
    """
    Wrap a synchronous generator (from retrieval.py) into an async generator
    that yields SSE-formatted strings. Runs each next() call in a thread
    so the event loop stays unblocked.
    """
    loop = asyncio.get_event_loop()
    sync_gen = sync_gen_func(*args)
    try:
        while True:
            event = await loop.run_in_executor(None, next, sync_gen)
            yield sse_format(event)
    except StopIteration:
        pass
    except Exception as e:
        yield sse_format({"type": "error", "error": str(e)})


# =============================================================================
# Health Check
# =============================================================================


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    pinecone_status = await asyncio.to_thread(check_pinecone_connection)

    health = {
        "status": "healthy",
        "pinecone": pinecone_status,
        "llm_configured": bool(config.LLM_MODEL_PATH),
        "config_valid": config.is_valid(),
        "missing_config": config.validate(),
    }

    if not config.is_valid() or not pinecone_status.get("connected"):
        health["status"] = "degraded"

    return health


# =============================================================================
# Streaming Endpoints (SSE)
# =============================================================================


@app.post("/api/explore_lost_time/stream")
async def explore_lost_time_stream(body: QueryRequest):
    """
    Streaming RAG endpoint using Server-Sent Events.

    SSE events:
        {"type": "token", "token": "..."}     - Individual tokens
        {"type": "sources", "passages": [...]} - Source passages
        {"type": "done", "done": true}         - Stream complete
    """
    query = body.query or body.message or ""

    if not query:
        return StreamingResponse(
            iter([sse_format({"type": "error", "error": "No query provided"})]),
            media_type="text/event-stream",
        )

    return StreamingResponse(
        async_sse_generator(stream_rag_response, query),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/reflect/stream")
async def reflect_stream(body: QueryRequest):
    """
    Streaming reflection endpoint using Server-Sent Events.

    SSE events:
        {"type": "token", "token": "..."}  - Individual tokens
        {"type": "done", "done": true}     - Stream complete
    """
    message = body.message or ""

    if not message:
        return StreamingResponse(
            iter([sse_format({"type": "error", "error": "No message provided"})]),
            media_type="text/event-stream",
        )

    return StreamingResponse(
        async_sse_generator(stream_reflect_response, message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# =============================================================================
# Non-Streaming Endpoints (Backward Compatible)
# =============================================================================


@app.post("/api/explore_lost_time", response_model=ExploreResponse)
async def explore_lost_time(body: QueryRequest):
    """Non-streaming RAG endpoint for passage retrieval."""
    query = body.query or body.message or ""

    if not query:
        return {"passages": []}

    try:
        result = await asyncio.to_thread(query_rag, query)
        return {
            "passages": result["passages"],
            "reply": result.get("reply", ""),
        }
    except Exception as e:
        # Fallback: return just passages without LLM summary
        try:
            docs = await asyncio.to_thread(retrieve_passages, query)
            passages = []
            for doc in docs:
                passages.append({
                    "book": doc.metadata.get("book", "Unknown"),
                    "chapter": doc.metadata.get("chapter", "Unknown"),
                    "text": doc.page_content,
                    "volume": doc.metadata.get("volume"),
                    "index": doc.metadata.get("index"),
                })
            return {"passages": passages, "error": str(e)}
        except Exception as inner_e:
            return ExploreResponse(passages=[], error=str(inner_e))


@app.post("/api/reflect", response_model=ReflectResponse)
async def reflect_on_day(body: QueryRequest):
    """Non-streaming reflection endpoint."""
    message = body.message or ""

    if not message:
        return {"reply": "No message received."}

    try:
        reply = await asyncio.to_thread(query_reflect, message)
        return {"reply": reply}
    except Exception as e:
        return {"reply": f"I apologize, but I encountered an error: {str(e)}"}


# =============================================================================
# Main
# =============================================================================


if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=5000, reload=config.DEBUG)
