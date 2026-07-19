# ProustGPT — Full Review Findings & Parallelized Fix Plan

**Date:** 2026-07-18
**Purpose:** Hand-off document for an orchestrator managing parallel agents. Every finding from a three-track review (backend architecture, frontend/product/UX, agentic orchestration) plus live browser verification, organized into independent workstreams with file boundaries, dependencies, proposed fixes, and acceptance criteria.

---

## 0. How to use this document

- Each **Workstream (A–K)** is a unit of work assignable to one agent. Workstreams list the files they touch; two workstreams that share no files can run in parallel.
- **Priority**: P0 = correctness/blocker, P1 = high-value, P2 = polish/refactor, P3 = strategic.
- Every finding has: evidence (file:line), proposed fix, and acceptance criteria.
- **Parallelization matrix and dependency notes are in §12.**
- Verification baseline: backend tests run via `cd backend && source venv/bin/activate && pytest`. Frontend builds via `npm run build`. Dev servers: `npm run dev` (5173) and `cd backend && venv/bin/python server.py` (5000). Retrieval evals: `cd evals` harness (see evals/README.md).

### System overview (context for agents)

- **Frontend:** React + Vite + TS in `src/`, styled-components, brown/cream literary theme, i18n EN/FR (`src/i18n/`), sessions in localStorage. Pages: LandingPage, ChatPage (1,322 lines), ReadPage + `components/ReadingView.tsx`, AboutPage.
- **Backend:** FastAPI in `backend/`. `server.py` (endpoints + SSE transport), `retrieval.py` (Pinecone→Cohere rerank→Groq RAG), `agent.py` (LangGraph ReAct agent, 6 Explore tools / 3 Reflect tools, heuristic router `needs_agent`), `corpus.py` (in-memory corpus), `config.py` (Pydantic settings).
- **Two modes:** Explore (`/api/explore_lost_time[/stream]`) and Reflect (`/api/reflect[/stream]`). Router sends complex/multi-turn Explore queries to the agent; Reflect always uses agent when `REFLECT_AGENT_ENABLED`.
- **SSE contract:** events `token | sources | metadata | status | done | error`; multi-line `data:` framing (512B lines); keepalives every 15s; client in `src/hooks/useStreamingQuery.ts`.
- **Models:** Groq `llama-3.3-70b-versatile` (kimi-k2 was retired), Cohere embed-v4.0 + rerank-v3.5, Pinecone `proust-index-v3` (dual EN/FR namespaces).

---

## 1. WORKSTREAM A — Agent correctness bugs (backend) — **P0**

**Files:** `backend/agent.py`, `backend/server.py` (agent-related lines only — coordinate with Workstream C/D if run concurrently; prefer sequencing A → C → D or one agent doing all three).

### A1. ContextVar passage accumulator is broken under the executor model
- **Evidence:** `backend/agent.py:36` declares `ContextVar("tool_passages", default=[])` — a shared mutable default list. `agent.py:395-397` calls `.set(passage_list)` inside the sync generator body, but the generator is advanced by `loop.run_in_executor(None, ...)` at `server.py:200`, which (unlike `asyncio.to_thread`) does **not** propagate contextvars, and successive `next()` calls may run on different pool threads. Tools append via `_tool_passages_var.get().extend(...)` (`agent.py:61`).
- **Impact:** Under concurrency: lost sources, cross-request passage contamination, slow memory leak into the module-level default list. Works today only by thread-reuse luck.
- **Fix:** Remove the ContextVar entirely. Build tools per-request with an explicit accumulator list closed over via `functools.partial` (or a small factory that returns `(tools, passage_list)`); alternatively run the whole generator on one dedicated thread fed through a queue. The shared-mutable-default `[]` must go regardless.
- **Accept:** A test running two interleaved agent streams (thread pool size ≥2) shows no passage leakage between requests; sources always emitted for the request that produced them.

### A2. Search tools never expose the global passage index → adjacent-passage chaining is mis-grounded
- **Evidence:** System prompt instructs "find the scene, then use get_adjacent_passages" (`agent.py:210`), but `search_passages`/`search_by_volume` output labels results with per-call `citation_index` (1..5 from `_format_passages`, `retrieval.py:314`), not the global corpus index (`agent.py:64-69`, `96-102`). The model therefore calls `get_adjacent_passages(passage_index=2)` and fetches corpus passages 0–4 (the opening of Swann's Way) regardless of search results. Free tools do print `[passage {index}]` correctly (`agent.py:150`, `175`).
- **Fix:** Include the global `index` in search-tool output, e.g. `[passage {p['index']}] [cite {n}] {vol} — {chapter}: {text}` — one line each at `agent.py:67` and `:99`. Update prompt if needed to say "pass the passage number shown in results."
- **Accept:** Trajectory test: after a search returning passage indices X..Y, a follow-up `get_adjacent_passages` call uses an index that appeared in the prior tool result (test would fail on current code).

### A3. Citation numbering diverges between model text and displayed sources
- **Evidence:** Each search call numbers results [1]..[5] locally; `_dedupe_sources` renumbers all accumulated passages globally 1..N (`agent.py:428-437`). After ≥2 searches the model's inline `[2]` (from search #2) points at what the UI shows as e.g. source [7].
- **Fix:** Make citation numbering globally monotonic within a request — number from `len(passage_list)` when formatting each search result, so tool-visible numbers equal final deduped numbers.
- **Accept:** Citation-integrity check: every `[n]` in the final reply maps to source n in the emitted sources events, in a 2-search scripted run.

### A4. Max-steps ends in an error — twice — instead of an answer
- **Evidence:** `steps_taken > AGENT_MAX_STEPS: break` (`agent.py:453-454`) only stops yielding status events; the graph keeps executing. Real cap is `recursion_limit = AGENT_MAX_STEPS*2+2` (`agent.py:442`); on hit, `GraphRecursionError` becomes a raw SSE `error` event (`server.py:218-220`); the frontend throws (`useStreamingQuery.ts:252-253`) and falls back to the **non-streaming endpoint which runs the entire agent again** (`server.py:361-362`), fails identically, then degrades to bare `retrieve_passages(query)`.
- **Fix:** Catch `GraphRecursionError` around `agent.stream(...)`; on catch, make one final tool-free LLM call ("answer from evidence gathered so far"), stream it, then sources + done. Remove or make the `steps_taken` break actually terminate.
- **Accept:** A forced recursion-limit run yields a coherent streamed answer + sources + done (no `error` event, no double agent execution).

### A5. Non-streaming fallback drops `lang`
- **Evidence:** `server.py:372` — fallback calls `retrieve_passages(query)` without `lang=lang`; a French user's error fallback silently retrieves English.
- **Fix:** Pass `lang=lang`.
- **Accept:** Fallback path test with `lang="fr"` asserts the FR namespace/pipeline is used.

### A6. Duplicated 90-line agent streaming bodies have already drifted
- **Evidence:** `stream_agent_response` (`agent.py:381-478`) vs `stream_reflect_agent_response` (`agent.py:505-592`) are copy-paste twins. Drift: explore emits full passage text in sources (`agent.py:438`) while reflect emits 200-char `_preview_passage` previews (`agent.py:555`) — contradicting the documented SSE-truncation design (previews over SSE, lazy-load full text via `/api/read/passage_text`). Comment at `agent.py:576` admits "same fix as explore agent."
- **Fix:** Extract one parameterized generator (prompt, tools, preview flag as args). Apply `_preview_passage` consistently to **all three** source-emitting paths (explore agent, reflect agent, fast RAG at `retrieval.py:361-362`).
- **Accept:** Single shared generator; grep shows one implementation; all sources events carry previews ≤ ~200 chars; frontend lazy-load still works.

### A7. Tool-surface hardening
- **Evidence:** `search_passages` and `search_by_volume` are ~30 identical lines differing by one metadata filter (`agent.py:42-103`). `lang` and `top_k` are model-chosen args — one omission by llama-3.3 and English passages leak into a French answer. No try/except in tool bodies; a Cohere 429 relies on LangGraph's default error-to-message behavior, burning steps.
- **Fix:** Merge into `search_passages(query, volume: int | None = None)`; bind `lang` at agent-construction time (closure/partial), drop `top_k` from the schema (fix at 5); wrap tool bodies in try/except returning actionable strings ("Search unavailable (rate limit) — use find_character_mentions instead").
- **Accept:** Tool schemas show no `lang`/`top_k`; FR session never yields EN passages; simulated Cohere failure returns a graceful tool message, not a crash.

### A8. LLM tool-calling fragility unhandled (Groq llama-3.3-70b)
- **Evidence:** `temperature=0.6` shared with generation (`config.py:24`); no validation of tool-call structure; tool-call JSON leaking as plain content would be chunk-streamed verbatim to the user (`agent.py:458-471`). Reflect's "at most 1 tool call" is prompt-only.
- **Fix:** Lower agent-path temperature (~0.2–0.3, separate config knob); detect/strip tool-call-syntax leaking into content before streaming; optionally add a per-mode hard tool-call cap enforced in the loop.
- **Accept:** Config exposes `AGENT_TEMPERATURE`; a content chunk matching tool-call JSON shape is suppressed/logged, not streamed.

---

## 2. WORKSTREAM B — Security & input hardening (backend) — **P0/P1**

**Files:** `backend/server.py` (request models, error paths), `backend/config.py`, `backend/requirements.txt`. Independent of A except both touch server.py — assign to one agent or sequence.

### B1. Open proxy: no auth, no rate limiting
- **Evidence:** All endpoints unauthenticated; anyone with the URL drains Groq/Cohere/Pinecone quota.
- **Fix:** Add `slowapi` per-IP rate limiting (e.g. 10 req/min on chat endpoints, higher on read endpoints). Auth optional for now; rate limit is the minimum.
- **Accept:** 429 returned past the limit; limit configurable via config.py.

### B2. No input size limits; client-controlled history
- **Evidence:** `QueryRequest` (`server.py:46-50`) has no max length on `query`/`message`; `history` unbounded and fully client-controlled, including fabricated `assistant` turns (prompt-injection surface).
- **Fix:** `Field(max_length=2000)` on query/message; server-side cap history to last N turns (e.g. 12); strip/limit per-message length.
- **Accept:** Oversized payloads → 422; long histories truncated server-side (test).

### B3. `lang` unvalidated
- **Evidence:** Used directly as Pinecone namespace and dict-key selector (`retrieval.py:176`).
- **Fix:** `lang: Literal["en", "fr", "both"]` on request models.
- **Accept:** Invalid lang → 422.

### B4. Exception messages leak to clients
- **Evidence:** `str(e)` in JSON/SSE error events (`server.py:220`, `383-385`, `409`).
- **Fix:** Log traceback server-side with a request ID; return generic message + ID.
- **Accept:** Error events contain no exception internals.

### B5. Config hygiene
- **Evidence:** `SECRET_KEY` defined, never used; `DEBUG: bool = True` is the production default (`config.py:35-36`). `backend/.env.bak` sits untracked (leak-by-`git add .` risk).
- **Fix:** Remove `SECRET_KEY` or use it; default `DEBUG=False`; add `.env.bak`/`.env*` to `.gitignore` (note: `backend/.env*` paths are permission-blocked for direct read in this environment — edit `.gitignore` only, do not read the env files).
- **Accept:** `git status` no longer shows `.env.bak`; DEBUG defaults false.

### B6. Errors return HTTP 200
- **Evidence:** `server.py:383`, `409` — all failures return 200 with error body; monitoring and Render health-restarts can't distinguish failure.
- **Fix:** Non-streaming endpoints: return 5xx on failure (SPA already handles). Streaming: keep in-band `error` events (SSE constraint) but count them in logs/metrics.
- **Accept:** Non-streaming failure test asserts 5xx.

---

## 3. WORKSTREAM C — Router & conversation history (backend) — **P1**

**Files:** `backend/agent.py` (`needs_agent`, `_COMPLEX_PATTERNS`), `backend/server.py` (route branches), `backend/retrieval.py` (`stream_rag_response` signature). Depends on A merging first if same-file edits (or same agent).

### C1. Fast path never receives history → follow-up amnesia
- **Evidence:** `stream_rag_response(query, lang)` has no history parameter (`server.py:289-290`, `retrieval.py:346`). A turn-2 follow-up ≥7 words matching no regex routes fast → answered with total amnesia ("What did you mean by involuntary memory in that answer?").
- **Fix:** Add a cheap query-condensation step (single small LLM call, or last-exchange concat) so the fast path can serve follow-ups with context.
- **Accept:** Scripted 2-turn conversation routed fast produces a contextually coherent answer (manual/eval check); `stream_rag_response` accepts history.

### C2. "≥2 user messages → agent forever"
- **Evidence:** `agent.py:333-336` — every conversation past turn 2 pays agent latency/cost permanently, even "what is a madeleine?".
- **Fix:** After C1 lands, route on the *current query's* complexity, not conversation length.
- **Accept:** Turn-3 simple query routes fast (unit test on `needs_agent`).

### C3. Regex router is brittle and English-only
- **Evidence:** `_COMPLEX_PATTERNS` (`agent.py:312-322`). False positives: "Tell me about the journey to Balbec" (`journey`), "relationship between Swann and Odette" for single-scene lookups. False negatives: "Which volume treats jealousy more deeply?", "what comes next" (pattern requires "what happens next", `agent.py:316`), multi-part questions. **French queries can never trigger the agent** ("comparez Swann et Charlus" → fast path) despite `lang=fr` threading everywhere else.
- **Fix (staged):** (1) Log every routing decision now: `{query, matched_rule, chose_agent}` (see K1). (2) Build a 50–100 query labeled router gold set (fast/agent), including FR queries. (3) Replace regex with embedding-nearest-centroid (Cohere embeds already paid for) or a sub-100-token structured-output LLM router call.
- **Accept:** Router accuracy measured against the gold set; FR comparative queries route to agent.

### C4. Unbounded history replay in agent
- **Evidence:** Full history rebuilt every turn (`agent.py:402-411`), no truncation/summarization; assistant turns carry stale `[1]`/`[2]` markers referencing invisible passages, inviting orphan citations.
- **Fix:** Cap replayed history (last N turns); strip citation markers from assistant history before replay.
- **Accept:** Unit test: 30-turn history → replayed messages ≤ cap and contain no `[n]` markers.

---

## 4. WORKSTREAM D — True agent streaming (backend) — **P1**

**Files:** `backend/agent.py` (stream loop). Sequence after A6 (shared generator) to avoid fixing the chunker twice.

### D1. Agent streaming is fake
- **Evidence:** `stream_mode="updates"` (`agent.py:443`) delivers the complete final AIMessage; code slices it into 12-char chunks (`agent.py:466-471`, reflect twin `580-587`) to simulate tokens. User waits full generation latency then gets a burst. The `_detect_repetition` check inside the chunk loop (`agent.py:472-473`) is theater — content is already generated/paid for. Fast path streams real tokens (`retrieval.py:372`).
- **Fix:** `stream_mode="messages"` (or `.astream_events`) to forward true tokens from the final LLM node; keep `updates` only for tool-call status events. Delete the chunker.
- **Accept:** Time-to-first-token on an agent query ≈ time of last tool call + LLM first token (not full completion); SSE event-order test still passes (`status* sources+ token+ done`).

### D2. Wall-clock timeout on agent runs
- **Fix:** Add an overall timeout (config knob); on expiry behave like A4's graceful degrade.
- **Accept:** Hung-LLM simulation ends with a degrade message within the timeout.

---

## 5. WORKSTREAM E — Caching, performance, reliability (backend) — **P1**

**Files:** `backend/retrieval.py`, `backend/server.py` (health), `backend/config.py`. Parallel-safe with F/G/H (frontend).

### E1. Zero caching anywhere
- **Evidence:** Identical queries re-pay Cohere embed → Pinecone → rerank → Pinecone fetch → Groq every time. No LRU on `embed_query`.
- **Fix:** TTL/LRU cache on query embeddings and on `(query, lang)` → retrieval results (retrieval only — never cache generation). Small dict + timestamps is fine.
- **Accept:** Second identical query hits cache (log/counter assertion); latency drop measurable in evals harness.

### E2. Health check hammers Pinecone
- **Evidence:** `/health` calls `describe_index_stats()` per hit (`retrieval.py:440-444`); Render (`render.yaml:6`) and Docker (`docker-compose.yml:12-17`) poll every ~30s.
- **Fix:** Cache stats module-level for ≥5 min.
- **Accept:** Two health calls within TTL → one Pinecone call (test with mock).

### E3. No timeouts/retries on external calls
- **Evidence:** Groq, Cohere, Pinecone use client defaults; one hung call occupies an executor thread indefinitely (keepalives keep the stream alive forever).
- **Fix:** Set `timeout`/`request_timeout` kwargs on ChatGroq/Cohere/Pinecone clients; conservative retries on idempotent calls (embed, query).
- **Accept:** Config exposes timeouts; simulated hang errors out within bound.

### E4. Dedicated bounded executor for SSE
- **Evidence:** All streams serialize through the default executor (`server.py:200`, ~5 threads on shared 0.5 CPU); streams starve health checks; realistic ceiling ~3–5 concurrent users.
- **Fix:** Dedicated `ThreadPoolExecutor(max_workers=N)` for SSE generators + queue-full 429. (Superseded long-term by K4 async rewrite.)
- **Accept:** Health endpoint stays responsive with N+2 concurrent streams (local load test).

### E5. HTTP caching for immutable read endpoints
- **Evidence:** `/api/read/toc` etc. serve immutable corpus data with no cache headers.
- **Fix:** `Cache-Control: public, max-age=86400` (or ETag) on read endpoints.
- **Accept:** Response headers present.

---

## 6. WORKSTREAM F — Frontend foundations: CSS reset, a11y, contrast — **P0/P1**

**Files:** `src/style.css`, `src/main.tsx`, `index.html`, small edits across `src/ChatPage.tsx`, `src/LandingPage.tsx`, `src/components/MarkdownMessage.tsx`, `src/components/PassageCard.tsx`. Parallel-safe with all backend workstreams. Coordinate with I (ChatPage refactor) — run F before I or same agent.

### F1. Untouched Vite template CSS sabotages the app — **P0**
- **Evidence:** `src/style.css` loaded globally by `main.tsx:3`: `:root { background-color: #242424; color-scheme: light dark }` (`style.css:8-16, 27-34`) → dark-gray flash before styled-components mount + dark-mode form-control mismatch on cream theme. `button:focus, button:focus-visible { outline: none }` (`style.css:82-85`) removes keyboard focus indication from **every button app-wide** (compounded by `GuidanceToggle`'s explicit `outline: none`, `LandingPage.tsx:368-370`). Template `a` colors `#646cff`, dark button styles, `.logo`/`.card` cruft remain. One accidental good: global `prefers-reduced-motion` rule (`style.css:100-106`) — keep it.
- **Fix:** Replace with a purpose-built reset: cream background on `:root`, `color-scheme: light`, visible `:focus-visible` outline style consistent with the theme, keep reduced-motion. Remove the `GuidanceToggle` outline suppression.
- **Accept:** No dark flash on hard reload; tabbing shows a visible focus ring on every interactive element; verified in browser.

### F2. Contrast failures (WCAG AA)
- **Evidence:** `#999` on `#f7f4f0` ≈ 2.8:1 — ResultsHeader (`ChatPage.tsx:206`), divider text, session dates, page info; placeholders `#a89888` ≈ 2.9:1; paragraph numbers `#ccc` (`ReadingView.tsx:89`).
- **Fix:** Lift meta text to ≥ `#767676` on cream; darken placeholders; paragraph numbers ≥ AA for incidental text or mark decorative.
- **Accept:** Spot-check the listed tokens ≥ 4.5:1 (or documented decorative exemption).

### F3. Keyboard/semantic gaps
- **Evidence:** `CitationRef` is a `span` with onClick — no role/tabIndex/keyboard (`MarkdownMessage.tsx:81-98, 133-141`). `SessionItem`/`SidebarItem` clickable div/li (`ChatPage.tsx:1079`, `1107`); `CardWrapper` clickable div (`PassageCard.tsx:401`). Chat input not in a `<form>` (`ChatPage.tsx:1271-1300`; mobile keyboards get no submit key) and uses deprecated `onKeyPress` (`ChatPage.tsx:1285`) — landing page does it correctly. Session delete `opacity: 0` until hover (`ChatPage.tsx:486`) — unreachable on touch; no delete confirmation. Back button bare "←" with no accessible name (`ChatPage.tsx:1150`); sidebar toggle lacks `aria-expanded`; no landmarks on ChatPage; split divider mouse-only, no `role="separator"`/keyboard/touch (`ChatPage.tsx:818-840`). Read-page chapter buttons expose no accessible name (verified via accessibility tree: unnamed `button` elements).
- **Fix:** Real `<button>`s or role+tabIndex+keydown; wrap chat input in `<form onSubmit>`; `onKeyDown`; always-visible (or focus-visible) delete affordance + confirm; aria-labels on icon buttons; `aria-expanded` on toggles; `<main>/<nav>` landmarks; divider `role="separator"` + arrow-key resize; name the chapter buttons.
- **Accept:** Keyboard-only pass: open sidebar, switch session, send message, open a citation, delete a session (with confirm) — all possible; accessibility tree shows named controls.

### F4. Misc visual/interaction rough edges
- **Evidence:** Stop appends literal `' [stopped]'` into saved message text (`ChatPage.tsx:995`) — untranslated meta-state persisted into content. Errors have no retry button (`ChatPage.tsx:1253-1257`). `text-align: justify` without `hyphens: auto` (MarkdownWrapper, PassageText, ReaderPanel) → rivers in narrow bubbles. Landing `ProustSection` absolutely positioned (`right: 8rem; top: 20rem`, `LandingPage.tsx:265-281`) — collides with chips at 768–1024px short viewports. Fonts: Belgrano loaded only at 400, IBM Plex Sans at 100/400 (`index.html:6`) but code requests 500/600 (`ChatPage.tsx:135`, `ReadPage.tsx:152`) → faux-bold; h1 `text-shadow` (`LandingPage.tsx:80`) reads dated. `height: 100vh` on chat (`ChatPage.tsx:38`) → iOS keyboard issue; use `100dvh`. Visible font-swap flash on landing (verified in browser: serif↔sans shift between first paint and hydration) — add `font-display: swap` review / preload.
- **Fix:** Store stopped-state as a message flag rendered via i18n; add retry button on error; `hyphens: auto` + lang attr; make ProustSection flow in grid/flex; load used font weights; drop text-shadow; `100dvh`; preload key fonts.
- **Accept:** Each item verified in browser at desktop + 800px + 375px.

### F5. i18n gaps
- **Evidence:** Interface key parity EN/FR is perfect (verified programmatically) but ChatPage empty-state suggestion pools are hardcoded English (`ChatPage.tsx:537-581`) — French users see English chips; `deriveTitle` fallback "New conversation" untranslated (`useChatSessions.ts:89`); `toLocaleDateString()` ignores selected locale (`ChatPage.tsx:1089`); bilingual reading always puts French first regardless of UI language with header "EN / FR" implying the opposite (`ReadingView.tsx:589-599`).
- **Fix:** Move suggestion pools into i18n files (landing already does this correctly); translate fallback; pass locale to date formatting; order columns by UI language and label them truthfully.
- **Accept:** FR UI shows FR chips/titles/dates; bilingual column order matches labels.

---

## 7. WORKSTREAM G — Mobile reader & responsive blockers — **P0**

**Files:** `src/components/ReadingView.tsx`, `src/LandingPage.tsx` (mobile CTA). Parallel-safe with everything except I if I touches these files.

### G1. Mobile pagination is impossible — **P0, browser-verified**
- **Evidence:** Only next/prev-page controls are the fixed SideArrows, `display: none` under 900px (`ReadingView.tsx:185-187`). Verified live at 375px: Overture "Page 1 of 39", scrolled to absolute bottom — sole "›" button computes `display:none`. Phone users can never reach page 2 of any chapter.
- **Fix:** Bottom prev/next pagination bar under 900px (sticky or end-of-content), with page X/Y indicator; optionally swipe.
- **Accept:** At 375px, navigate Overture page 1 → 2 → back; verified in browser.

### G2. "Begin reading" invisible on mobile
- **Evidence:** Portrait + Read CTA block `display: none` under 768px (`LandingPage.tsx:278-280`); only the small top-nav "Read" remains. Half the product is a footnote on phones.
- **Fix:** Add a visible Read CTA under the search pill on mobile.
- **Accept:** 375px landing shows a Read entry point above the fold or immediately below chips.

### G3. Bilingual toggle label is a no-op ternary
- **Evidence:** `{bilingual ? 'EN / FR' : 'EN / FR'}` (`ReadingView.tsx:558`) — identical string both states; users can't tell what the toggle does or which state is active.
- **Fix:** State-communicating label (e.g. "EN only" ↔ "EN + FR") + pressed styling/`aria-pressed`.
- **Accept:** Toggle label/state visibly changes; `aria-pressed` correct.

---

## 8. WORKSTREAM H — Product improvements — **P1/P2**

**Files:** `src/LandingPage.tsx`, `src/AboutPage.tsx`, `src/ChatPage.tsx` (header/sidebar), `src/hooks/useChatSessions.ts`, i18n files, potentially new `src/components/ReadingPaths*`; backend `reading_paths.json` (exists, unused by any frontend surface).

### H1. Bilingual reading — the differentiator — is nearly invisible
- **Evidence:** Only entry point is the broken toggle (G3) inside a chapter; nothing on landing, About, or TOC mentions side-by-side French.
- **Fix:** Promote on landing (one line + visual) and About; mention in TOC header.
- **Accept:** A first-time visitor can discover bilingual reading without entering a chapter first.

### H2. `refine_prose` → `reflect` rename (mode identity drift) — browser-verified
- **Evidence:** Internal mode name is `refine_prose` (`LandingPage.tsx:539`, `ChatPage.tsx:980`); session tag colors `refine_prose` **blue** `#5a78a0` (`ChatPage.tsx:465-471`) while every other Reflect surface is sage green `#5a6b5a`. Verified live: blue "Reflect" tag in sidebar next to green chips.
- **Fix:** Rename mode value to `reflect` everywhere + localStorage migration for old sessions (map `refine_prose` → `reflect` on load in `useChatSessions`); unify accent color to sage green.
- **Accept:** Old sessions still load; all Reflect surfaces one color.

### H3. No mode switching mid-conversation
- **Evidence:** Header mode label inert (`ChatPage.tsx:1151`); switching requires "+ Explore / + Reflect" in a sidebar closed by default for new users.
- **Fix:** Mode switcher in the chat header (starts a new mode-scoped conversation, with confirm if mid-thread).
- **Accept:** Mode switch reachable without opening the sidebar.

### H4. Guided reading paths — unshipped feature with data already present
- **Evidence:** `backend/reading_paths.json` exists (per CLAUDE.md), no frontend uses it; "New to Proust?" audience needs exactly this.
- **Fix:** Backend endpoint to serve paths; make "New to Proust?" open a paths surface (e.g. cards → deep-link into ReadPage sections).
- **Accept:** A path can be followed end-to-end from the landing page.

### H5. Retention & shallow features
- **Evidence:** Hardcoded Characters list just pre-fills "Tell me about X" (`ChatPage.tsx:1050-1058`); no export/share of conversations or bookmarks; Reflect (a journaling surface) has no continuity between sessions.
- **Fix (pick per capacity):** export/share bookmarks + conversations (markdown/clipboard); "passage of the day"; Reflect session recall ("last time you reflected on…") — client-side from localStorage is enough initially.
- **Accept:** At least bookmark/conversation export ships.

### H6. Stale README screenshot
- **Evidence:** `screenshot-1.png` shows an older landing design (six plain prompt boxes) that no longer matches shipped code.
- **Fix:** Re-capture.

---

## 9. WORKSTREAM I — Frontend code health refactors — **P2**

**Files:** `src/ChatPage.tsx` (split into `ChatSidebar`, `MessageList`, `ChatInput`, `chatStyles.ts`), new `src/prompts.ts`, `src/components/PassageCard.tsx` + `ReaderPanel.tsx` (shared extraction), `src/hooks/useLocalStorage.ts`, `src/styles/theme.ts`, `src/utils/`, `src/components/ReadingView.tsx`, `src/ReadPage.tsx`. **Run after F/G/H merge** (heavy same-file overlap), or assign F+G+H+I to one agent sequenced.

### I1. ChatPage god component
- **Evidence:** 1,322 lines: ~500 lines styled-components, two prompt pools, session orchestration, stream-commit logic, bookmark logic, split-pane drag, all rendering. Init effect is a 60-line branching state machine with `// eslint-disable` and empty deps (`ChatPage.tsx:697-755`).
- **Fix:** Split as above; move init state machine into `useChatSessions` or a `useChatBootstrap` hook.
- **Accept:** No file >400 lines in the chat feature; behavior unchanged (manual smoke: new chat both modes, stream, stop, citation click, delete).

### I2. PassageCard/ReaderPanel duplication (~150 lines)
- **Evidence:** Identical `isTruncated`, `fetchFullText`, `fetchFrenchText`, EN/FR display resolution, `sourceLabel`, NavFooter/NavArrow/Dot (`PassageCard.tsx:270-338, 393-398` vs `ReaderPanel.tsx:249-330, 166-208`).
- **Fix:** Extract `usePassageText(passage)` hook + shared `<PassageNav>`.
- **Accept:** One implementation; both surfaces still lazy-load full/FR text.

### I3. theme.ts is dead weight
- **Evidence:** No ThemeProvider anywhere; `theme.ts` imported by nothing; `#8b4513` hand-copied 100+ times.
- **Fix:** Either wire `ThemeProvider` or export token constants and sweep-replace; current half-state is the worst option.
- **Accept:** Grep for `#8b4513` in components ≈ 0 (tokens only).

### I4. Bookmark identity breaks against SSE previews
- **Evidence:** Bookmarks keyed on text equality (`ChatPage.tsx:1004-1021`); a passage bookmarked from its 200-char preview never matches its lazily-loaded full text. Also `Bookmark` interface declared 4× (`ChatPage.tsx:594`, `ReadPage.tsx:15`, `ReadingView.tsx:241`, `BookmarkDropdown.tsx:5`).
- **Fix:** Key on `passage.index`; single shared `Bookmark` type + migration for existing stored bookmarks.
- **Accept:** Bookmark from a collapsed card, expand card, star state stays consistent; old bookmarks migrate.

### I5. useLocalStorage stale-closure + multi-consumer clobbering
- **Evidence:** Functional updates apply against captured `storedValue` (`useLocalStorage.ts:31`); ChatPage/ReadingView/ReadPage each hold independent `'proust-bookmarks'` state — a stale copy can clobber a newer write.
- **Fix:** Functional-setState form reading latest; sync via `storage` event or a shared context/store for bookmarks.
- **Accept:** Add bookmark in reader panel, then trigger a ChatPage bookmark write — first bookmark survives.

### I6. Router bypass & DOM mutation hacks
- **Evidence:** ReadingView mutates history with `window.history.pushState` + synthetic `PopStateEvent` (`ReadingView.tsx:515-516, 525-526`), caught by a hand-rolled listener (`ReadPage.tsx:215-222`); highlight effect mutates DOM styles with nested `setTimeout`s (`ReadingView.tsx:413-432`).
- **Fix:** `useSearchParams` end-to-end; highlight via state/CSS classes.
- **Accept:** Back/forward navigation through reader states works; no synthetic events.

### I7. Dead code & small correctness
- **Evidence:** `counter.ts`, `typescript.svg` (Vite leftovers), `src/utils/clipboard.ts` (never imported), `TextLanguageSwitcher.tsx` (never imported), empty `StreamingBubble` extension (`ChatPage.tsx:171`), write-only `setVolumeNameEn` (`ReadingView.tsx:333`). Citation regex matches single digits only `\[(\d)\]` (`ChatPage.tsx:614`, `MarkdownMessage.tsx:116`) — silently wrong if `RETRIEVAL_K` > 9. `characters` array re-created every render. `shuffleArray` + prompt pools duplicated landing/chat and drifted. `API_BASE_URL` re-derived in 5 files with inline fetch — no API client module.
- **Fix:** Delete dead files; `\[(\d+)\]`; hoist constants; single `prompts.ts` (i18n-keyed, see F5); small `src/api.ts` client.
- **Accept:** Build passes; grep confirms removals; citations work for [10]+ if k raised.

---

## 10. WORKSTREAM J — Testing & evaluation — **P1**

**Files:** `backend/tests/*` (new files), `evals/*` (extend), `backend/evaluation.py` (retire). Parallel-safe with frontend workstreams; coordinate with A/C/D since it tests their surfaces (write tests against the *fixed* behavior; ideally same agent or after).

### J1. Agent layer has zero tests and zero evals — the strategic gap
- **Evidence:** No `test_agent*.py`; `conftest.py` mocks `needs_agent` to always-False (`conftest.py:102-103, 157`) so the router is never executed by any test; no line of agent.py has coverage. `evals/` is explicitly retrieval-only ("does not call the app's LLM", evals/README.md:179) — the comparative/multi-hop queries the agent exists for are exactly what nothing measures.
- **Fix (three cheap layers, consistent with the repo's no-LLM-judge philosophy):**
  1. **Router accuracy:** 50–100 labeled queries (fast/agent, EN+FR) → assert accuracy threshold; unit tests for `needs_agent` edge cases.
  2. **Trajectory checks:** ~20 multi-hop questions with mechanical assertions — "comparative query ⇒ ≥2 distinct search calls"; "adjacent-passage question ⇒ `get_adjacent_passages` called with an index that appeared in a prior tool result" (catches A2 regressions).
  3. **Citation integrity:** every `[n]` in the reply has source n in emitted passages (catches A3 regressions).
- **Accept:** All three layers runnable from `evals/` or pytest; at least one agent-path test runs de-mocked (recorded/stubbed LLM acceptable).

### J2. Unit tests for pure logic (currently highest-value untested surface)
- **Evidence:** Zero tests for: `needs_agent`, `_COMPLEX_PATTERNS`, context stitching (`_starts_mid_sentence` etc.), `_format_passages`, `_detect_repetition`, `sse_format` line-splitting, `_dedupe_sources`, all of `corpus.py` (TOC/chapter functions are mocked even in read-endpoint tests). No concurrency tests (A1 would never be caught).
- **Fix:** Deterministic unit tests for each; small fixture corpus for corpus.py; a two-interleaved-streams concurrency test.
- **Accept:** Listed functions covered; concurrency test in suite.

### J3. Retire `evaluation.py`
- **Evidence:** Hardcodes a 15-question dataset duplicating the newer 111-question `evals/` gold set; LLM-as-judge uses the same Groq model being evaluated (`evaluation.py:235`) with silent `except: return 0.5` (`evaluation.py:172-173`) — self-grading with a neutral default masks failures.
- **Fix:** Delete or archive; fold anything unique into `evals/`; if LLM-judging returns, different model family + loud failures.
- **Accept:** One evaluation system remains.

---

## 11. WORKSTREAM K — Observability, deployment, strategic — **P1/P3**

**Files:** `backend/server.py`, `backend/agent.py`, `backend/retrieval.py` (logging lines), `Dockerfile`, `render.yaml`, `backend/requirements.txt`.

### K1. Structured logging + request IDs — **P1, prerequisite for C3 router work**
- **Evidence:** Effectively no observability by default: uvicorn access logs only; LangSmith opt-in-off (`config.py:55`); `@traceable` covers retrieval helpers but nothing in agent.py; no log of routing decision, tools called, steps, latency, cost. Lifespan uses `print()` (`server.py:93-101`). Minor: `sse_format` calls `logger.info` unconditionally per event (`server.py:164`) — every 12-char token — while everything else gates behind `SSE_DEBUG`.
- **Fix:** One JSON log line per request: `{request_id, route, chose_agent, matched_rule, tools: [(name, args, ms)], steps, recursion_hit, retrieval_count, total_ms, reply_len}`. `@traceable` on agent stream fns. Gate the per-event log behind `SSE_DEBUG`. Replace prints with logging.
- **Accept:** A single chat request produces exactly one structured summary line; agent traces visible in LangSmith when enabled.

### K2. Deployment/config drift
- **Evidence:** `render.yaml:15` pins `proust-index-v2`; real index is v3; `config.py:19` defaults to `proust-index` — three answers to "which index?". Dockerfile installs spaCy + `en_core_web_sm` (`Dockerfile:32-33`) for code the server never runs. `metadata.py` and `connection_mapper.py` are imported by nothing in the serving path and import `sentence_transformers` which is **not in requirements.txt** (would crash on import) — they're offline preprocessing tools.
- **Fix:** Align index to v3 everywhere (or make it required); drop spaCy from the image; move `metadata.py`/`connection_mapper.py` to `scripts/`.
- **Accept:** One index name; image builds smaller; no missing-dep landmines in serving path.

### K3. Server-side sessions — **P3**
- **Evidence:** History entirely client-side, replayed fully every request (`server.py:277, 322`); no LangGraph checkpointing (agent rebuilt every request, `agent.py:413, 532`).
- **Fix (when warranted):** Session ID + Redis/SQLite storing history and LangGraph checkpoints; enables server-side truncation/summarization, agent memory, and stops trusting client-fabricated history.

### K4. Async end-to-end — **P3, highest-leverage scalability change**
- **Evidence:** Sync pipeline in executor threads is the root cause of E4's ceiling and A1's hazard class.
- **Fix:** langchain-groq/cohere/pinecone async clients; native async generators replace `async_sse_generator` machinery. Eliminates the thread-pool ceiling and the ContextVar hazard class entirely.

### K5. Router upgrade — **P3** (see C3; do after K1 logging produces data.)

---

## 12. Parallelization & sequencing guide

**Safe to run fully in parallel (disjoint files):**
- Group 1 (backend): A (+C+D as one sequenced agent — heavy `agent.py`/`server.py` overlap), B can be a second backend agent if it coordinates on `server.py` request models only, E (retrieval.py/health — minor server.py touch), K1/K2.
- Group 2 (frontend): F, G, H — G touches ReadingView/Landing; F touches style.css + small edits; H touches Landing/About/sessions. Minor Landing overlap between F4/G2/H1 — either sequence those three findings or assign F+G+H to one agent.
- Group 3: J (tests/evals) — parallel with frontend; for agent-behavior tests, run after A/C/D land (write tests against fixed behavior).

**Hard dependencies:**
- A6 (shared generator) **before** D1 (kill fake streaming) — avoid deleting the chunker twice.
- C1 (fast path history) **before** C2 (relax router rule).
- K1 (routing logs) **before** C3 stage 3 / K5 (router replacement) — need data.
- F (CSS reset/a11y foundations) **before** I (ChatPage split) — same files.
- H2 (mode rename) needs its localStorage migration shipped **with** the rename in one change.
- I4 (bookmark keying) should land **with or after** A6's consistent preview behavior.

**Suggested wave plan:**
- **Wave 1 (parallel):** [A→C→D one agent] · [B] · [E] · [F+G one agent] · [K1+K2]
- **Wave 2 (parallel):** [H] · [J] · [I]
- **Wave 3 (strategic, as capacity allows):** K3, K4, K5, H4/H5 remainder.

**Global verification after each wave:** `pytest` (backend), `npm run build`, browser smoke on both modes (send, stream, stop, citations, bookmarks), 375px reader pagination, FR-language pass, and the evals harness for retrieval regressions.
