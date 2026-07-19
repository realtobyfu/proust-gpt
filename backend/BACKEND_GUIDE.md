# ProustGPT Backend Guide

A deep-dive into how the backend works, from first principles up to the full request lifecycle.

---

## Part 1: Python Generators & `yield` (Foundation)

A regular function runs to completion and returns once:
```python
def add(a, b):
    return a + b   # done, function is gone from memory
```

A **generator function** uses `yield` and can be paused/resumed:
```python
def count_up():
    print("starting")
    yield 1        # pause, send 1 to caller
    print("resumed")
    yield 2        # pause, send 2 to caller
    print("done")
    # function ends here — StopIteration is raised automatically

gen = count_up()   # does NOT run yet — creates a generator object
next(gen)          # prints "starting", returns 1
next(gen)          # prints "resumed", returns 2
next(gen)          # prints "done", raises StopIteration
```

**Generators are lazy** — they compute nothing until asked. This is why they're perfect for streaming: you can yield tokens from an LLM as they arrive, without buffering the entire response first.

In `retrieval.py`:
```python
def stream_rag_response(query, passages, ...):
    # ... setup ...
    for chunk in llm.stream(prompt):           # LLM hands back chunks one at a time
        yield {"type": "token", "token": chunk.content}   # immediately sent to browser
    yield {"type": "sources", "passages": [...]}
    yield {"type": "done", "done": True}
```

The caller loops over this generator and forwards each dict to the browser. The browser renders each token as it lands — that's the "typing" effect.

---

## Part 2: `asyncio` — Concurrency Without Threads

### The Problem: Waiting is Wasteful

A web server needs to handle many requests at once. Consider a naive synchronous server:

```python
def handle_request(query):
    result = call_pinecone(query)   # blocks for 200ms — server does NOTHING else
    result = call_cohere(result)    # blocks another 100ms
    return result
```

If 100 users hit the server simultaneously, users 2–100 are stuck waiting for user 1 to finish. That's a queue, not a server.

### The `asyncio` Solution: Cooperative Multitasking

Python's `asyncio` runs a single-threaded **event loop**. Instead of blocking while waiting for I/O, a coroutine yields control back to the loop so other coroutines can run:

```python
import asyncio

async def fetch_data():          # "async def" marks this as a coroutine
    print("fetching...")
    await asyncio.sleep(1)       # "await" yields control back to event loop
    print("done")                # event loop resumes us after 1 second
    return "data"

async def main():
    # run two fetches concurrently — total time ~1s, not ~2s
    result1, result2 = await asyncio.gather(
        fetch_data(),
        fetch_data()
    )
```

**Key rule:** `await` can only appear inside `async def`. Think of `await` as "I'm going to wait for this; let other things run in the meantime."

### `asyncio.to_thread()` — Bridging Sync and Async

Most third-party libraries (LangChain, Cohere, Pinecone) are **synchronous** — they block until done. You can't just `await` them. The solution is `asyncio.to_thread()`, which runs blocking code in a background thread so it doesn't freeze the event loop:

```python
# In server.py:
async def explore_stream(...):
    # retrieve_passages() is synchronous (blocks) — move it off the event loop
    passages = await asyncio.to_thread(
        retrieve_passages, query, lang=lang
    )
    # while Pinecone is thinking, the event loop can serve other requests
```

This is the core pattern the backend uses everywhere. The event loop stays free; slow I/O runs in threads.

---

## Part 3: FastAPI — The Web Framework

FastAPI is built on top of `asyncio`. It handles HTTP, parses requests, validates data with Pydantic, and calls your handler functions.

### Basic Structure

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class QueryRequest(BaseModel):   # Pydantic model — auto-validates incoming JSON
    query: str
    lang: str = "en"             # optional with default

@app.post("/api/explore")
async def explore(request: QueryRequest):   # FastAPI calls this when POST /api/explore arrives
    result = await asyncio.to_thread(retrieve_passages, request.query)
    return {"passages": result}  # auto-serialized to JSON
```

When a request comes in:
1. FastAPI parses the HTTP body
2. Pydantic validates it against `QueryRequest` (raises 422 if invalid)
3. FastAPI calls your `async def` handler
4. Your handler `await`s slow work, returning JSON when done

### Pydantic: Data Validation

Pydantic models describe the shape of data. They're used for both request parsing and response formatting:

```python
# From server.py:
class QueryRequest(BaseModel):
    query: str | None = None
    message: str | None = None    # alternative field name
    lang: str = "en"
    history: list[HistoryMessage] = []

class HistoryMessage(BaseModel):
    role: str       # "user" or "assistant"
    content: str
```

If a request arrives without `lang`, Pydantic fills in `"en"`. If `query` is the wrong type, Pydantic rejects it with a clear error — no manual validation code needed.

### Lifespan: Startup & Shutdown

`server.py` uses a **lifespan context manager** to run setup once when the server starts:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- startup ---
    initialize_clients()    # connects to Pinecone, Cohere, Groq
    yield                   # server is now running and handling requests
    # --- shutdown --- (cleanup goes here if needed)

app = FastAPI(lifespan=lifespan)
```

This ensures clients are initialized before any request is handled, not lazily on the first request (which could be slow or cause race conditions).

### CORS Middleware

Browsers block cross-origin requests by default. Since the frontend runs on `localhost:5173` and backend on `localhost:5000`, CORS headers are needed:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,   # ["http://localhost:5173"] in dev
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Part 4: SSE — Server-Sent Events (Streaming to the Browser)

SSE is a simple protocol: the server holds the HTTP connection open and sends newline-delimited text events. The browser reads them one by one.

**Wire format:**
```
data: {"type": "token", "token": "Marcel"}\n\n
data: {"type": "token", "token": " remembered"}\n\n
data: {"type": "done", "done": true}\n\n
```

Each `data:` line is one event. Double newline = event boundary.

**FastAPI implementation using `StreamingResponse`:**
```python
from fastapi.responses import StreamingResponse

@app.post("/api/explore_lost_time/stream")
async def explore_stream(request: QueryRequest):
    async def event_generator():
        async for event in async_sse_generator(request.query):
            json_str = json.dumps(event)
            yield f"data: {json_str}\n\n"   # SSE format

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",      # disable nginx buffering
        }
    )
```

`async_sse_generator()` in `server.py` is the bridge between the sync `stream_rag_response()` generator (which yields dicts) and the async world. It runs the sync generator in a thread and pulls events out via an `asyncio.Queue`, so the event loop is never blocked while waiting for the next LLM token.

---

## Part 5: Pydantic Settings — `config.py`

`pydantic-settings` extends Pydantic to read from environment variables and `.env` files:

```python
# config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    pinecone_api_key: str = ""
    llm_model_name: str = "moonshotai/kimi-k2-instruct"
    retrieval_candidates: int = 20

config = Config()   # reads .env on import
```

Usage throughout the codebase:
```python
from config import config

llm = ChatGroq(api_key=config.groq_api_key, model=config.llm_model_name)
```

Pydantic automatically coerces types: if `RETRIEVAL_CANDIDATES=30` is a string in `.env`, it becomes the integer `30` in Python.

---

## Part 6: pytest — Testing the Backend

### Basics

```python
# tests/test_example.py

def test_add():
    assert 1 + 1 == 2   # passes

def test_fail():
    assert 1 + 1 == 3   # fails — pytest shows a diff
```

Run with `pytest` from the project root. pytest auto-discovers files named `test_*.py` and functions named `test_*`.

### Fixtures — Reusable Setup

Fixtures are functions decorated with `@pytest.fixture` that provide test dependencies:

```python
import pytest

@pytest.fixture
def mock_passages():
    return [{"text": "Swann's Way...", "volume": 1}]

def test_format_response(mock_passages):   # pytest injects mock_passages automatically
    result = format_response(mock_passages)
    assert "Swann" in result
```

`conftest.py` defines fixtures available to all tests in the directory — no import needed.

### Mocking External Services

The tests mock out Pinecone, Groq, and Cohere so tests run offline:

```python
# tests/conftest.py
from unittest.mock import patch, MagicMock

@pytest.fixture
def client():
    with patch("retrieval.query_rag", return_value=(mock_passages, "mock reply")), \
         patch("retrieval.check_pinecone_connection", return_value=True):
        from server import app
        from fastapi.testclient import TestClient
        yield TestClient(app)
```

`TestClient` wraps the FastAPI app and lets you call HTTP endpoints in tests without running a real server:

```python
def test_explore(client):
    response = client.post("/api/explore_lost_time", json={"query": "madeleine"})
    assert response.status_code == 200
    data = response.json()
    assert "passages" in data
    assert "reply" in data
```

### Testing Streaming Endpoints

SSE responses come back as a text blob. The `_parse_sse()` helper in `test_server.py` splits it into events:

```python
def _parse_sse(text: str) -> list[dict]:
    events = []
    for line in text.strip().split("\n"):
        if line.startswith("data:"):
            events.append(json.loads(line[5:].strip()))
    return events

def test_streaming(client):
    with client.stream("POST", "/api/explore_lost_time/stream",
                       json={"query": "madeleine"}) as r:
        events = _parse_sse(r.text)

    types = [e["type"] for e in events]
    assert "token" in types
    assert "done" in types
    assert types[-1] == "done"   # done event must be last
```

---

## Part 7: How It All Fits Together

Here's the full request lifecycle for a streaming query:

```
Browser
  │  POST /api/explore_lost_time/stream
  │  {"query": "madeleine memory"}
  ▼
FastAPI (event loop thread)
  │  1. Parses + validates QueryRequest with Pydantic
  │  2. Calls async explore_stream() handler
  ▼
server.py: explore_stream()
  │  3. await asyncio.to_thread(retrieve_passages, query)
  │     → runs in thread pool, event loop free for other requests
  ▼
retrieval.py: retrieve_passages() [in thread]
  │  4. Cohere: embed query → vector
  │  5. Pinecone: vector search → 20 candidates
  │  6. Cohere: rerank → top 5 passages
  │  returns passages
  ▼
server.py (back on event loop)
  │  7. Creates stream_rag_response() generator
  │  8. Wraps it in async_sse_generator()
  │     → runs sync generator in thread
  │     → pulls events via asyncio.Queue
  ▼
retrieval.py: stream_rag_response() [in thread]
  │  9. yield {"type": "sources", "passages": [...]}
  │  10. for chunk in llm.stream(prompt):
  │          yield {"type": "token", "token": chunk}
  │  11. yield {"type": "done", "done": True}
  ▼
server.py: StreamingResponse
  │  12. Each yielded dict → "data: {...}\n\n" → sent to browser immediately
  ▼
Browser
  │  13. Reads each "data:" line as it arrives
  │  14. Renders tokens one by one → typing effect
```

The key insight: `asyncio.to_thread()` is the bridge everywhere. The event loop handles HTTP and async coordination; threads handle blocking I/O (Pinecone, Cohere, Groq).

---

## Quick Reference

| Concept | What it does | Where in this codebase |
|---|---|---|
| `yield` | Produces values lazily, pauses function | `retrieval.py: stream_rag_response()` |
| `async def` | Declares a coroutine (can be paused) | All FastAPI handlers in `server.py` |
| `await` | Pauses coroutine until result is ready | `await asyncio.to_thread(...)` |
| `asyncio.to_thread()` | Runs blocking code in a thread | Wrapping all sync library calls |
| `StreamingResponse` | Holds HTTP connection open, streams data | SSE endpoints in `server.py` |
| `BaseModel` (Pydantic) | Validates + parses request/response JSON | `QueryRequest`, `PassageItem` etc. |
| `BaseSettings` (Pydantic) | Reads config from `.env` file | `config.py` |
| `@pytest.fixture` | Reusable test setup | `tests/conftest.py` |
| `TestClient` | Tests HTTP endpoints without a running server | `tests/test_server.py` |
| `patch()` | Replaces real services with mocks in tests | `tests/conftest.py` |
