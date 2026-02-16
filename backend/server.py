"""
ProustGPT FastAPI Backend

Provides both streaming (SSE) and non-streaming endpoints for:
- RAG-based passage retrieval from Proust's "In Search of Lost Time"
- Proustian-style reflection conversations
"""
import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import uvicorn
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import config
from corpus import get_table_of_contents, get_chapter_passages, get_passage_text, locate_passage
from retrieval import (
    query_rag,
    query_reflect,
    stream_rag_response,
    stream_reflect_response,
    check_pinecone_connection,
    retrieve_passages,
    initialize_clients,
)
from agent import stream_agent_response, query_agent, needs_agent, stream_reflect_agent_response, query_reflect_agent


# =============================================================================
# Pydantic request/response models
# =============================================================================


class HistoryMessage(BaseModel):
    role: str
    content: str


class QueryRequest(BaseModel):
    query: Optional[str] = None
    message: Optional[str] = None
    lang: Optional[str] = "en"
    history: Optional[list[HistoryMessage]] = None


class PassageItem(BaseModel):
    book: str
    chapter: str
    text: str
    text_fr: Optional[str] = None
    volume: Optional[int] = None
    index: Optional[int] = None
    citation_index: Optional[int] = None
    relevance_summary: Optional[str] = None


class ExploreResponse(BaseModel):
    passages: list[PassageItem] = []
    reply: str = ""
    error: Optional[str] = None


class ReflectResponse(BaseModel):
    reply: str
    passages: list[PassageItem] = []


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
    """Validate configuration and initialize API clients on startup."""
    missing = config.validate()
    if missing:
        print(f"WARNING: Missing required configuration: {missing}")
        print("Some features may not work. See .env.example for setup instructions.")
    else:
        try:
            await asyncio.to_thread(initialize_clients)
            print("API clients initialized successfully")
        except Exception as e:
            print(f"WARNING: Failed to initialize API clients: {e}")
            print("Clients will be initialized lazily on first request.")
    yield


app = FastAPI(title="ProustGPT", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in config.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# SSE helpers
# =============================================================================


logger = logging.getLogger("proust.sse")


SSE_LINE_MAX = 512


def sse_format(data: dict) -> str:
    """Format data as SSE event, splitting across multiple data: lines if needed.

    The SSE spec allows multiple `data:` lines per event — the client concatenates
    them.  Splitting large JSON payloads keeps each line under proxy line-size
    limits (e.g. Render's reverse proxy), preventing mid-JSON truncation.
    """
    payload = json.dumps(data)
    event_type = data.get("type", "?")
    size = len(payload.encode("utf-8"))
    logger.info(f"SSE event type={event_type} payload={size}B")

    if size <= SSE_LINE_MAX:
        return f"data: {payload}\n\n"

    # Split across multiple data: lines for proxy safety
    lines = []
    for i in range(0, len(payload), SSE_LINE_MAX):
        lines.append(f"data: {payload[i:i + SSE_LINE_MAX]}\n")
    lines.append("\n")  # blank line = event boundary
    logger.info(f"SSE event type={event_type} split into {len(lines) - 1} data lines")
    return "".join(lines)


KEEPALIVE_INTERVAL = 15  # seconds between SSE keepalive comments


async def async_sse_generator(sync_gen_func, *args) -> AsyncGenerator[str, None]:
    """
    Wrap a synchronous generator (from retrieval.py) into an async generator
    that yields SSE-formatted strings. Runs each next() call in a thread
    so the event loop stays unblocked.

    Sends SSE comment keepalives (`: keepalive\\n\\n`) every KEEPALIVE_INTERVAL
    seconds while waiting for the sync generator. This prevents reverse proxies
    (e.g. Render) from dropping idle connections during long blocking operations
    like Pinecone queries or Cohere reranking.
    """
    loop = asyncio.get_event_loop()
    sync_gen = sync_gen_func(*args)
    try:
        while True:
            # Schedule next(sync_gen) in a thread — don't cancel it on timeout
            future = loop.run_in_executor(None, next, sync_gen)
            task = asyncio.ensure_future(future)

            while True:
                done, _ = await asyncio.wait({task}, timeout=KEEPALIVE_INTERVAL)
                if done:
                    break
                # Still waiting — send keepalive comment to prevent proxy timeout
                logger.debug("SSE keepalive sent")
                yield ": keepalive\n\n"

            event = task.result()
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
        "llm_configured": bool(config.GROQ_API_KEY),
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

    Routes complex/follow-up queries through the LangGraph agent,
    simple queries through the fast single-shot pipeline.

    SSE events:
        {"type": "status", "status": "..."}   - Agent status updates
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

    lang = body.lang or "en"
    history = [m.model_dump() for m in body.history] if body.history else None

    if needs_agent(query, history):
        return StreamingResponse(
            async_sse_generator(stream_agent_response, query, history, lang),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    return StreamingResponse(
        async_sse_generator(stream_rag_response, query, lang),
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

    Routes through the reflect agent (with optional corpus search) when
    enabled, falls back to pure LLM streaming otherwise.

    SSE events:
        {"type": "status", "status": "..."}   - Agent status updates
        {"type": "token", "token": "..."}      - Individual tokens
        {"type": "sources", "passages": [...]} - Source passages (when agent finds relevant text)
        {"type": "done", "done": true}         - Stream complete
    """
    message = body.message or ""

    if not message:
        return StreamingResponse(
            iter([sse_format({"type": "error", "error": "No message provided"})]),
            media_type="text/event-stream",
        )

    lang = body.lang or "en"
    history = [m.model_dump() for m in body.history] if body.history else None

    if config.REFLECT_AGENT_ENABLED:
        return StreamingResponse(
            async_sse_generator(stream_reflect_agent_response, message, history, lang),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    return StreamingResponse(
        async_sse_generator(stream_reflect_response, message, lang),
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

    lang = body.lang or "en"
    history = [m.model_dump() for m in body.history] if body.history else None

    try:
        if needs_agent(query, history):
            result = await asyncio.to_thread(query_agent, query, history, lang)
        else:
            result = await asyncio.to_thread(query_rag, query, lang)
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
                    "text_fr": doc.metadata.get("_text_fr") or doc.metadata.get("text_fr"),
                    "volume": doc.metadata.get("volume"),
                    "index": doc.metadata.get("index"),
                })
            return {"passages": passages, "error": str(e)}
        except Exception as inner_e:
            return ExploreResponse(passages=[], error=str(inner_e))


@app.post("/api/reflect")
async def reflect_on_day(body: QueryRequest):
    """Non-streaming reflection endpoint."""
    message = body.message or ""

    if not message:
        return {"reply": "No message received."}

    lang = body.lang or "en"
    history = [m.model_dump() for m in body.history] if body.history else None

    try:
        if config.REFLECT_AGENT_ENABLED:
            result = await asyncio.to_thread(query_reflect_agent, message, history, lang)
            return {
                "reply": result["reply"],
                "passages": result.get("passages", []),
            }
        reply = await asyncio.to_thread(query_reflect, message, lang)
        return {"reply": reply}
    except Exception as e:
        return {"reply": f"I apologize, but I encountered an error: {str(e)}"}


# =============================================================================
# Read Proust Endpoints (no API keys needed)
# =============================================================================


@app.get("/api/read/toc")
async def read_toc(
    lang: str = Query("en", description="Language for names: en or fr"),
):
    """Return the full table of contents for browsing."""
    return get_table_of_contents(lang=lang)


@app.get("/api/read/locate")
async def read_locate(
    index: int = Query(..., description="Passage index to locate"),
):
    """Resolve a passage index to its reading page location."""
    result = locate_passage(index)
    if result is None:
        return {"error": "Passage not found"}
    return result


@app.get("/api/read/chapter")
async def read_chapter(
    volume: int = Query(..., description="Volume number (1-7)"),
    chapter: str = Query(..., description="Chapter name"),
    offset: int = Query(0, ge=0, description="Passage offset"),
    limit: int = Query(20, ge=1, le=100, description="Number of passages"),
    lang: str = Query("en", description="Text language: en, fr, or both"),
):
    """Return paginated passages for a chapter."""
    result = get_chapter_passages(volume, chapter, offset, limit, lang=lang)
    if result is None:
        return {"error": "Chapter not found", "passages": []}
    return result


@app.get("/api/read/passage_text")
async def read_passage_text(
    index: int = Query(..., description="Passage index"),
    lang: str = Query("en", description="Text language: en, fr, or both"),
):
    """Return text for a single passage, optionally in French."""
    result = get_passage_text(index, lang=lang)
    if result is None:
        return {"error": "Passage not found"}
    return result


# =============================================================================
# Static file serving (production: Docker serves frontend + backend together)
# =============================================================================

if config.SERVE_STATIC and os.path.isdir(config.STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(config.STATIC_DIR, "assets")), name="static-assets")

    @app.get("/{full_path:path}")
    async def spa_catch_all(request: Request, full_path: str):
        """Serve static files if they exist, otherwise index.html for SPA routing."""
        if full_path:
            file_path = os.path.join(config.STATIC_DIR, full_path)
            # Prevent path traversal
            if os.path.realpath(file_path).startswith(os.path.realpath(config.STATIC_DIR)) \
               and os.path.isfile(file_path):
                return FileResponse(file_path)
        return FileResponse(os.path.join(config.STATIC_DIR, "index.html"))


# =============================================================================
# Main
# =============================================================================


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=config.PORT, reload=config.DEBUG)
