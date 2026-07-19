# ProustGPT Redesign Context: Two Modes + Agentic Orchestration

Prepared from current codebase and git history in `/Users/realtobyfu/Documents/proust-gpt`.

## 1) Redesign Timeline From Git History (Key Commits)

| Date | Commit | What changed | Why it matters to the blog narrative |
|---|---|---|---|
| 2026-02-14 | `e3eff2c` | Introduced LangGraph ReAct agent tools and complexity routing in backend | Marks shift from single-shot RAG toward agentic orchestration |
| 2026-02-15 | `4e2e2e1` | Added reflect agentic mode + UI/backend wiring | Establishes explicit two-mode product model (Explore + Reflect) |
| 2026-02-15 | `a1adcc4` | Added “new chat” controls for both modes | UX makes mode-switching first-class |
| 2026-02-16 | `8f6359e` | LLM response persistence improvements | Hardens chat continuity during streaming/navigation |
| 2026-02-16 | `ec38efe` | Stream passages individually for Render proxy limits | Starts reliability-focused SSE transport hardening |
| 2026-02-16 | `5103154` | EN/FR stream handling + logging improvements | Improves bilingual stream behavior and observability |
| 2026-02-16 | `2c2b58f` | Multi-line SSE protocol support | Fixes JSON truncation/pathological SSE parsing |
| 2026-02-16 | `8fc48cb` | SSE keepalive | Prevents idle proxy disconnects during long backend calls |
| 2026-03-03 | `72be7e4` | SSE stream termination fix | Eliminates generator-end/transport edge case failures |
| 2026-03-03 | `4d2d998` | Streaming commit diagnostics in frontend | Improves debugging for “stream completed but UI didn’t commit” issues |

Suggested framing: this was not a one-shot redesign; it was a staged architecture migration followed by transport hardening.

## 2) Current Two-Mode Product Architecture

### Mode model

- **Explore mode** (`explore_lost_time` in UI): literary analysis + retrieval-heavy flow.
- **Reflect mode** (`refine_prose` in UI): introspective conversation, with optional lightweight corpus grounding.

In chat send logic, UI mode maps to API mode:

```ts
// src/ChatPage.tsx
const queryMode = activeMode === 'refine_prose' ? 'reflect' : 'explore';
await streamQuery(message, queryMode, language, history.length > 0 ? history : undefined);
```

### Landing/page-level mode entry points

```ts
// src/LandingPage.tsx
navigate('/chat', { state: { mode: 'explore_lost_time', prompt: inputValue.trim() } });
...
onClick={() => handleChipClick('refine_prose', t(chip.promptKey))}
```

### Backend routing shape

- Explore stream endpoint: `/api/explore_lost_time/stream`
- Reflect stream endpoint: `/api/reflect/stream`
- Both have non-streaming fallbacks.

```py
# backend/server.py
@app.post("/api/explore_lost_time/stream")
async def explore_lost_time_stream(body: QueryRequest):
    ...
    if needs_agent(query, history):
        return StreamingResponse(async_sse_generator(stream_agent_response, query, history, lang), ...)
    return StreamingResponse(async_sse_generator(stream_rag_response, query, lang), ...)

@app.post("/api/reflect/stream")
async def reflect_stream(body: QueryRequest):
    ...
    if config.REFLECT_AGENT_ENABLED:
        return StreamingResponse(async_sse_generator(stream_reflect_agent_response, message, history, lang), ...)
    return StreamingResponse(async_sse_generator(stream_reflect_response, message, lang), ...)
```

## 3) Agentic Orchestration Design (Current)

### 3.1 Complexity router (Explore mode)

The architecture does not force every query through LangGraph. It routes based on query complexity + history depth:

```py
# backend/agent.py
def needs_agent(query: str, history: list[dict] | None = None) -> bool:
    if not config.AGENT_ENABLED:
        return False

    if history:
        user_msgs = [m for m in history if m.get("role") == "user"]
        if len(user_msgs) >= 2:
            return True

    if _COMPLEX_PATTERNS.search(query):
        return True

    if history and len(query.split()) <= 6:
        return True

    return False
```

Interpretation: simple first-turn questions stay fast/cheap; comparative or follow-up questions get multi-step tool reasoning.

### 3.2 Tooling asymmetry between modes

Explore has 6 tools; Reflect intentionally has 3.

```py
# backend/agent.py
_TOOLS = [
    search_passages,
    search_by_volume,
    get_adjacent_passages,
    get_chapter_overview,
    find_character_mentions,
    get_toc,
]

_REFLECT_TOOLS = [
    search_passages,
    get_adjacent_passages,
    find_character_mentions,
]
```

This asymmetry is core to the redesign story: **mode is not just UI skin; it changes tool budget and reasoning behavior**.

### 3.3 Reflect mode prompt policy

Reflect agent prompt explicitly says default to pure conversation and search only when resonance is specific.

```py
# backend/agent.py (excerpt)
"""... Your DEFAULT mode is pure introspective conversation — most responses should NOT use tools at all. Only search when the user's experience strongly echoes a specific Proustian theme or moment.

WHEN TO SEARCH (use at most 1 tool call):
- A vivid sensory memory...
- Returning to a childhood place...
- Jealousy...
..."""
```

### 3.4 Shared retrieval pipeline beneath both paths

Agent tools and fast RAG share the same semantic retrieval core:

```py
# backend/retrieval.py
def retrieve_passages(query: str, lang: str = "en") -> list[Document]:
    candidates = _pinecone_query(query, top_k=config.RETRIEVAL_CANDIDATES, lang=lang)
    reranker = get_reranker()
    reranked = list(reranker.compress_documents(candidates, query))
    return _stitch_context(reranked, lang=lang)
```

Current defaults in config:

```py
# backend/config.py
RETRIEVAL_CANDIDATES: int = 20
RERANK_TOP_N: int = 5
AGENT_ENABLED: bool = True
REFLECT_AGENT_ENABLED: bool = True
AGENT_MAX_STEPS: int = 4
```

## 4) SSE Event-Oriented Orchestration (and why it evolved)

### 4.1 Event contract

Frontend handles these event types:

```ts
// src/hooks/useStreamingQuery.ts
type: 'token' | 'sources' | 'metadata' | 'status' | 'done' | 'error';
```

### 4.2 Sources-before-tokens ordering in agent path

Agent stream now pushes deduped sources before first text token:

```py
# backend/agent.py (excerpt)
for src_event in _dedupe_sources():
    yield src_event

for i in range(0, len(content), chunk_size):
    chunk = content[i:i + chunk_size]
    yield {"type": "token", "token": chunk}
```

This is important for resilience: passage context can still reach the UI even if later stream chunks are interrupted.

### 4.3 Multi-line SSE framing for proxy safety

Server splits oversized JSON into multiple `data:` lines:

```py
# backend/server.py
if size <= SSE_LINE_MAX:
    return f"data: {payload}\n\n"

lines = []
for i in range(0, len(payload), SSE_LINE_MAX):
    lines.append(f"data: {payload[i:i + SSE_LINE_MAX]}\n")
lines.append("\n")
return "".join(lines)
```

Client reassembles those lines before JSON parse:

```ts
// src/hooks/useStreamingQuery.ts
const dataLines = block.split('\n')
  .filter(l => l.startsWith('data: '))
  .map(l => l.slice(6));
const jsonStr = dataLines.join('');
const event: StreamEvent = JSON.parse(jsonStr);
```

### 4.4 Keepalive + final-buffer flush

Keepalive prevents idle disconnects; final-buffer flush handles no-trailing-delimiter edge case:

```py
# backend/server.py
done, _ = await asyncio.wait({task}, timeout=KEEPALIVE_INTERVAL)
if not done:
    yield ": keepalive\n\n"
```

```ts
// src/hooks/useStreamingQuery.ts
buffer += decoder.decode();
if (buffer.trim()) {
  const remaining = buffer.split('\n\n');
  for (const block of remaining) processSSEBlock(block);
}
```

## 5) Frontend Mode + Session Orchestration

Mode is persisted as session metadata, not only transient UI state.

```ts
// src/hooks/useChatSessions.ts
export interface ChatSession {
  id: string;
  title: string;
  mode: string;
  ...
}
```

New conversations can be explicitly mode-scoped:

```tsx
// src/ChatPage.tsx
<NewChatButton $mode="explore" onClick={() => handleNewConversation('explore_lost_time')}>
  + {t('chat.modeExplore')}
</NewChatButton>
<NewChatButton $mode="reflect" onClick={() => handleNewConversation('refine_prose')}>
  + {t('chat.modeReflect')}
</NewChatButton>
```

Recent reliability-focused commit also added commit-phase diagnostics in message persistence flow:

```ts
// src/ChatPage.tsx
logStreamCommit('commit effect entered', {
  responseLength: streamingResponse.length,
  passages: finalPassages.length,
});
```

## 6) Test Evidence You Can Cite

Backend tests explicitly validate stream event ordering and both mode routes.

```py
# backend/tests/test_server.py
assert types == ["status", "sources", "token", "token", "token", "done"]
```

```py
# backend/tests/test_server.py
resp = client.post("/api/reflect/stream", json={"message": "I had a good day"})
assert "text/event-stream" in resp.headers["content-type"]
```

## 7) Suggested Blog Structure (Ready to Expand)

1. **Why redesign at all**: from one conversational flow to dual-intent product (analysis vs introspection).
2. **Mode split**: explain semantic difference, not just UI tabs.
3. **Agentic orchestration**: complexity router + tool loops for Explore.
4. **Reflect philosophy**: default no-tools stance, optional retrieval only when resonance is specific.
5. **Transport reality**: production SSE issues (proxy line limits, idle timeouts, truncated tails) and concrete fixes.
6. **Product polish**: session-mode persistence + “new chat per mode” UX + streaming commit reliability.
7. **What changed in engineering mindset**: architecture migration followed by hardening.

## 8) Useful File Index For Writing

- `backend/agent.py` (tool definitions, router, agent stream logic)
- `backend/server.py` (mode endpoints, SSE wrapper, keepalive, framing)
- `backend/retrieval.py` (shared retrieval + stream behavior)
- `backend/config.py` (feature flags + defaults)
- `src/ChatPage.tsx` (mode UX, mode->API mapping, stream commit logic)
- `src/hooks/useStreamingQuery.ts` (SSE parser, fallback strategy)
- `src/hooks/useChatSessions.ts` (session persistence with mode)
- `backend/tests/test_server.py` (behavior assertions)
- `README.md` + `architecture.html` + `data-flow.html` (author-facing architecture narrative)

