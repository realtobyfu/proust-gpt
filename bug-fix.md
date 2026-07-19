# Bug Fix: Passage Cards Loading Forever on Render

## Symptom

On the Render deployment, the LLM response text streams correctly (including citation references like [1], [2], [3]), but the passage cards below the response are stuck in an infinite loading state. This only happens on Render - locally, everything works fine.

## Root Cause (Two-Part)

### 1. Backend: `sources` SSE event sent AFTER all tokens

The SSE stream sends events in this order:

```
status → status → token → token → ... → token → sources → done
```

The `sources` event (which carries all passage data) was the **second-to-last** event in the stream. On Render's reverse proxy, the final events in an SSE stream can be **buffered or dropped** before reaching the client. Even with `X-Accel-Buffering: no` and `Cache-Control: no-cache` headers, Render's infrastructure sometimes doesn't forward the tail end of a stream reliably.

This affected three code paths:
- `retrieval.py` `stream_rag_response()` — fast RAG pipeline
- `agent.py` `stream_agent_response()` — LangGraph explore agent
- `agent.py` `stream_reflect_agent_response()` — LangGraph reflect agent

### 2. Frontend: Remaining SSE buffer discarded when stream ends

In `useStreamingQuery.ts`, the SSE parsing loop splits on `\n\n` delimiters:

```typescript
const lines = buffer.split('\n\n');
buffer = lines.pop() || ''; // Keep incomplete message in buffer
```

When the ReadableStream reports `done: true`, the loop exits immediately **without processing whatever remains in `buffer`**. If the server closes the connection and the final SSE events don't have a trailing `\n\n`, they stay in the buffer and are silently lost.

Locally, the connection closes cleanly and events arrive with proper delimiters. On Render's proxy, the final TCP segment may not include the trailing `\n\n`, causing the `sources` event to be stranded.

### Combined Effect

The frontend never receives the `sources` event → `streamingPassages` stays empty → when streaming completes, the AI message is created with `passages: undefined` → no PassageCards render (or they render with empty data, appearing to load forever).

## Fix

### Backend: Send `sources` BEFORE tokens

**`retrieval.py`** (fast RAG path):
```python
# BEFORE (sources at end):
for chunk in llm.stream(prompt):
    yield {"type": "token", "token": chunk.content}
yield {"type": "sources", "passages": passages}  # could be lost!

# AFTER (sources first):
yield {"type": "sources", "passages": passages}   # sent early!
for chunk in llm.stream(prompt):
    yield {"type": "token", "token": chunk.content}
```

**`agent.py`** (agent paths):
```python
# BEFORE: sources sent after all tokens at the end of the generator

# AFTER: sources sent just before the first token
# When the agent emits its final text response (no tool_calls),
# all tool calls are already done and passage_list is fully populated.
# We deduplicate and yield sources right before the first token.
```

This ensures the `sources` event arrives during the middle of the stream (where proxy buffering is not an issue) rather than at the tail end.

### Frontend: Process remaining buffer after stream ends

**`useStreamingQuery.ts`**:
```typescript
// After the while loop exits:
buffer += decoder.decode(); // flush any remaining bytes
if (buffer.trim()) {
  const remaining = buffer.split('\n\n');
  for (const line of remaining) {
    processSSELine(line);  // same processing as inside the loop
  }
}
```

This is a **defense-in-depth** fix. Even if the backend fix ensures sources arrive early, the frontend now correctly handles any SSE events that arrive in the final buffer.

## Files Changed

| File | Change |
|------|--------|
| `backend/retrieval.py` | Moved `sources` yield before LLM token streaming |
| `backend/agent.py` | Send `sources` before first token in both `stream_agent_response` and `stream_reflect_agent_response` |
| `src/hooks/useStreamingQuery.ts` | Extract `processSSELine` helper; flush and process remaining buffer after stream ends |

## Lessons Learned

1. **SSE event ordering matters in proxied environments.** Critical data should be sent early in the stream, not at the tail end. Reverse proxies (Render, nginx, Cloudflare) can buffer or drop the final events.

2. **Always process the remaining buffer.** When parsing a chunked stream, the final chunk may not have a trailing delimiter. After the stream closes, flush the decoder and process whatever remains.

3. **Test with a reverse proxy.** Streaming behavior that works on `localhost` may break behind a proxy. The `X-Accel-Buffering: no` header helps but isn't a complete guarantee.

4. **Defense in depth.** Fix both the backend (send data early) AND the frontend (handle edge cases in parsing). Either fix alone would likely solve the issue, but both together make the system robust.
