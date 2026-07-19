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
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Literal, Optional

import uvicorn
from fastapi import FastAPI, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

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
from agent import stream_agent_response, query_agent, needs_agent, route_query, stream_reflect_agent_response, query_reflect_agent


# =============================================================================
# Pydantic request/response models
# =============================================================================


class HistoryMessage(BaseModel):
    role: str
    content: str = Field(default="", max_length=config.MAX_QUERY_CHARS)


class QueryRequest(BaseModel):
    # B2: bound user-supplied text; B3: validate lang.
    query: Optional[str] = Field(default=None, max_length=config.MAX_QUERY_CHARS)
    message: Optional[str] = Field(default=None, max_length=config.MAX_QUERY_CHARS)
    lang: Literal["en", "fr"] = "en"
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


logging.basicConfig(
    level=logging.DEBUG if config.DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("proust.sse")
req_logger = logging.getLogger("proust.request")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate configuration and initialize API clients on startup."""
    missing = config.validate()
    if missing:
        req_logger.warning("Missing required configuration: %s", missing)
        req_logger.warning("Some features may not work. See .env.example for setup.")
    else:
        try:
            await asyncio.to_thread(initialize_clients)
            req_logger.info("API clients initialized successfully")
        except Exception as e:  # noqa: BLE001
            req_logger.warning("Failed to initialize API clients: %s", e)
            req_logger.warning("Clients will be initialized lazily on first request.")
    yield
    # NB: the module-level _SSE_EXECUTOR is intentionally NOT shut down here — it
    # lives for the process lifetime and is shared across the app's lifespan(s).


# Rate limiting (B1) — per-IP. Disabled automatically under tests via config.
limiter = Limiter(
    key_func=get_remote_address,
    enabled=config.RATE_LIMIT_ENABLED,
    default_limits=[],
)

app = FastAPI(title="ProustGPT", lifespan=lifespan)
app.state.limiter = limiter


async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"error": "Rate limit exceeded. Please slow down."})


app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

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


SSE_LINE_MAX = 512
SSE_DEBUG = os.getenv("PROUST_STREAM_DEBUG", "").lower() in {"1", "true", "yes", "on"}

if SSE_DEBUG:
    logger.setLevel(logging.INFO)

# Dedicated bounded executor for SSE generators (E4) so long streams can't
# starve the default thread pool (health checks, read endpoints).
_SSE_EXECUTOR = ThreadPoolExecutor(
    max_workers=config.SSE_MAX_WORKERS, thread_name_prefix="sse"
)


def _new_request_id() -> str:
    return uuid.uuid4().hex[:12]


def _sse_debug(message: str, *args) -> None:
    """Emit SSE diagnostics only when explicit stream debugging is enabled."""
    if SSE_DEBUG:
        logger.info(message, *args)


def _callable_name(fn) -> str:
    """Best-effort name for functions, partials, and test doubles."""
    return (
        getattr(fn, "__name__", None)
        or getattr(fn, "_mock_name", None)
        or fn.__class__.__name__
    )


def _next_sse_event(sync_gen) -> tuple[bool, Optional[dict]]:
    """Pull one event from a sync generator without leaking StopIteration."""
    try:
        return True, next(sync_gen)
    except StopIteration:
        return False, None


def sse_format(data: dict) -> str:
    """Format data as SSE event, splitting across multiple data: lines if needed.

    The SSE spec allows multiple `data:` lines per event — the client concatenates
    them.  Splitting large JSON payloads keeps each line under proxy line-size
    limits (e.g. Render's reverse proxy), preventing mid-JSON truncation.
    """
    payload = json.dumps(data)
    event_type = data.get("type", "?")
    size = len(payload.encode("utf-8"))
    _sse_debug("SSE event type=%s payload=%dB", event_type, size)

    if size <= SSE_LINE_MAX:
        return f"data: {payload}\n\n"

    # Split across multiple data: lines for proxy safety
    lines = []
    for i in range(0, len(payload), SSE_LINE_MAX):
        lines.append(f"data: {payload[i:i + SSE_LINE_MAX]}\n")
    lines.append("\n")  # blank line = event boundary
    _sse_debug("SSE event type=%s split into %d data lines", event_type, len(lines) - 1)
    return "".join(lines)


KEEPALIVE_INTERVAL = 15  # seconds between SSE keepalive comments


async def async_sse_generator(sync_gen_func, *args, summary: Optional[dict] = None) -> AsyncGenerator[str, None]:
    """
    Wrap a synchronous generator (from retrieval.py) into an async generator
    that yields SSE-formatted strings. Runs each next() call in a thread
    so the event loop stays unblocked.

    Sends SSE comment keepalives (`: keepalive\\n\\n`) every KEEPALIVE_INTERVAL
    seconds while waiting for the sync generator. This prevents reverse proxies
    (e.g. Render) from dropping idle connections during long blocking operations
    like Pinecone queries or Cohere reranking.

    If `summary` is provided, one structured JSON log line is emitted when the
    stream closes (K1), with token/source counts, error status, and latency.
    """
    loop = asyncio.get_running_loop()
    sync_gen = sync_gen_func(*args)
    fn_name = _callable_name(sync_gen_func)
    stream_id = f"{fn_name}:{id(sync_gen):x}"
    _sse_debug("SSE stream start id=%s fn=%s", stream_id, fn_name)
    tokens = sources = statuses = 0
    errored = False
    started = time.monotonic()
    try:
        while True:
            # Schedule next(sync_gen) on the dedicated SSE executor (E4) —
            # don't cancel it on timeout.
            future = loop.run_in_executor(_SSE_EXECUTOR, _next_sse_event, sync_gen)
            task = asyncio.ensure_future(future)

            while True:
                done, _ = await asyncio.wait({task}, timeout=KEEPALIVE_INTERVAL)
                if done:
                    break
                # Still waiting — send keepalive comment to prevent proxy timeout
                logger.debug("SSE keepalive sent")
                yield ": keepalive\n\n"

            has_event, event = task.result()
            if not has_event:
                _sse_debug("SSE stream exhausted id=%s", stream_id)
                break
            event_type = event.get("type", "?") if isinstance(event, dict) else "?"
            if event_type == "token":
                tokens += 1
            elif event_type == "sources":
                sources += 1
            elif event_type == "status":
                statuses += 1
            elif event_type == "error":
                errored = True
            _sse_debug("SSE stream id=%s yielded event=%s", stream_id, event_type)
            yield sse_format(event)
    except Exception as e:  # noqa: BLE001 — surface a generic in-band error (B4)
        errored = True
        req_logger.exception("SSE stream failure id=%s", stream_id)
        yield sse_format({"type": "error", "error": "The stream failed unexpectedly. Please try again."})
    finally:
        _sse_debug("SSE stream close id=%s", stream_id)
        if summary is not None:
            summary.update(
                tokens=tokens, sources=sources, statuses=statuses,
                errored=errored, total_ms=round((time.monotonic() - started) * 1000),
            )
            req_logger.info("request %s", json.dumps(summary))


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


_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


@app.post("/api/explore_lost_time/stream")
@limiter.limit(config.CHAT_RATE_LIMIT)
async def explore_lost_time_stream(request: Request, body: QueryRequest):
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

    lang = body.lang
    history = [m.model_dump() for m in body.history] if body.history else None
    chose_agent, matched_rule = route_query(query, history)
    summary = {
        "request_id": _new_request_id(),
        "route": "explore",
        "chose_agent": chose_agent,
        "matched_rule": matched_rule,
        "lang": lang,
        "query_len": len(query),
    }

    if chose_agent:
        gen = async_sse_generator(stream_agent_response, query, history, lang, summary=summary)
    else:
        gen = async_sse_generator(stream_rag_response, query, lang, history, summary=summary)

    return StreamingResponse(gen, media_type="text/event-stream", headers=_SSE_HEADERS)


@app.post("/api/reflect/stream")
@limiter.limit(config.CHAT_RATE_LIMIT)
async def reflect_stream(request: Request, body: QueryRequest):
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

    lang = body.lang
    history = [m.model_dump() for m in body.history] if body.history else None
    summary = {
        "request_id": _new_request_id(),
        "route": "reflect",
        "chose_agent": config.REFLECT_AGENT_ENABLED,
        "lang": lang,
        "query_len": len(message),
    }

    if config.REFLECT_AGENT_ENABLED:
        gen = async_sse_generator(stream_reflect_agent_response, message, history, lang, summary=summary)
    else:
        gen = async_sse_generator(stream_reflect_response, message, lang, summary=summary)

    return StreamingResponse(gen, media_type="text/event-stream", headers=_SSE_HEADERS)


# =============================================================================
# Non-Streaming Endpoints (Backward Compatible)
# =============================================================================


@app.post("/api/explore_lost_time", response_model=ExploreResponse)
@limiter.limit(config.CHAT_RATE_LIMIT)
async def explore_lost_time(request: Request, body: QueryRequest):
    """Non-streaming RAG endpoint for passage retrieval."""
    query = body.query or body.message or ""

    if not query:
        return {"passages": []}

    lang = body.lang
    history = [m.model_dump() for m in body.history] if body.history else None
    request_id = _new_request_id()
    chose_agent, matched_rule = route_query(query, history)
    started = time.monotonic()

    try:
        if chose_agent:
            result = await asyncio.to_thread(query_agent, query, history, lang)
        else:
            result = await asyncio.to_thread(query_rag, query, lang, history)
        req_logger.info("request %s", json.dumps({
            "request_id": request_id, "route": "explore", "streaming": False,
            "chose_agent": chose_agent, "matched_rule": matched_rule, "lang": lang,
            "total_ms": round((time.monotonic() - started) * 1000),
            "reply_len": len(result.get("reply", "")),
        }))
        return {"passages": result["passages"], "reply": result.get("reply", "")}
    except Exception:  # noqa: BLE001 — log details, return generic 5xx (B4/B6)
        req_logger.exception("explore failed request_id=%s", request_id)
        return JSONResponse(
            status_code=500,
            content={"passages": [], "reply": "",
                     "error": f"Internal error (ref {request_id})."},
        )


@app.post("/api/reflect")
@limiter.limit(config.CHAT_RATE_LIMIT)
async def reflect_on_day(request: Request, body: QueryRequest):
    """Non-streaming reflection endpoint."""
    message = body.message or ""

    if not message:
        return {"reply": "No message received."}

    lang = body.lang
    history = [m.model_dump() for m in body.history] if body.history else None
    request_id = _new_request_id()

    try:
        if config.REFLECT_AGENT_ENABLED:
            result = await asyncio.to_thread(query_reflect_agent, message, history, lang)
            return {"reply": result["reply"], "passages": result.get("passages", [])}
        reply = await asyncio.to_thread(query_reflect, message, lang)
        return {"reply": reply}
    except Exception:  # noqa: BLE001 — log details, return generic 5xx (B4/B6)
        req_logger.exception("reflect failed request_id=%s", request_id)
        return JSONResponse(
            status_code=500,
            content={"reply": f"I encountered an error (ref {request_id}). Please try again."},
        )


# =============================================================================
# Read Proust Endpoints (no API keys needed)
# =============================================================================


# Read endpoints serve immutable corpus data — allow long-lived caching (E5).
_READ_CACHE_CONTROL = "public, max-age=86400"
ReadLang = Literal["en", "fr", "both"]

_READING_PATHS_FILE = os.path.join(os.path.dirname(__file__), "reading_paths.json")
_reading_paths_cache: Optional[dict] = None


def _load_reading_paths() -> dict:
    """Load and cache the guided reading-paths data (H4)."""
    global _reading_paths_cache
    if _reading_paths_cache is None:
        try:
            with open(_READING_PATHS_FILE, encoding="utf-8") as f:
                _reading_paths_cache = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            req_logger.warning("Failed to load reading_paths.json: %s", e)
            _reading_paths_cache = {"paths": {}}
    return _reading_paths_cache


@app.get("/api/read/paths")
async def read_paths(response: Response):
    """Return the guided reading paths (New-to-Proust journeys)."""
    response.headers["Cache-Control"] = _READ_CACHE_CONTROL
    return _load_reading_paths()


@app.get("/api/read/toc")
async def read_toc(
    response: Response,
    lang: ReadLang = Query("en", description="Language for names: en or fr"),
):
    """Return the full table of contents for browsing."""
    response.headers["Cache-Control"] = _READ_CACHE_CONTROL
    return get_table_of_contents(lang=lang)


@app.get("/api/read/locate")
async def read_locate(
    response: Response,
    index: int = Query(..., ge=1, description="Passage index to locate"),
):
    """Resolve a passage index to its reading page location."""
    result = locate_passage(index)
    if result is None:
        return {"error": "Passage not found"}
    response.headers["Cache-Control"] = _READ_CACHE_CONTROL
    return result


@app.get("/api/read/chapter")
async def read_chapter(
    response: Response,
    volume: int = Query(..., description="Volume number (1-7)"),
    chapter: str = Query(..., max_length=200, description="Chapter name"),
    offset: int = Query(0, ge=0, description="Passage offset"),
    limit: int = Query(20, ge=1, le=100, description="Number of passages"),
    lang: ReadLang = Query("en", description="Text language: en, fr, or both"),
):
    """Return paginated passages for a chapter."""
    result = get_chapter_passages(volume, chapter, offset, limit, lang=lang)
    if result is None:
        return {"error": "Chapter not found", "passages": []}
    response.headers["Cache-Control"] = _READ_CACHE_CONTROL
    return result


@app.get("/api/read/passage_text")
async def read_passage_text(
    response: Response,
    index: int = Query(..., ge=1, description="Passage index"),
    lang: ReadLang = Query("en", description="Text language: en, fr, or both"),
):
    """Return text for a single passage, optionally in French."""
    result = get_passage_text(index, lang=lang)
    if result is None:
        return {"error": "Passage not found"}
    response.headers["Cache-Control"] = _READ_CACHE_CONTROL
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
