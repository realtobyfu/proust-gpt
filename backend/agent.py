"""
LangGraph ReAct agent for ProustGPT.

Provides a tool-calling agent that can decompose complex literary questions
into multiple targeted searches across the Proust corpus, with conversation
memory for follow-up questions.

Concurrency model (A1): each request builds its own set of tools closed over a
per-request `_PassageAccumulator`. There is no shared mutable state — safe under
the thread-pool executor regardless of contextvar propagation.
"""
import logging
import re
import time
from typing import Generator, Optional

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool
from langgraph.errors import GraphRecursionError
from langgraph.prebuilt import create_react_agent

from config import config
from corpus import (
    get_table_of_contents,
    get_chapter_passages,
    get_passage_text,
    search_passages_by_text,
)
from retrieval import (
    _pinecone_query,
    _stitch_context,
    _format_passages,
    _preview_passage,
    cap_history,
    get_llm,
    get_agent_llm,
    get_reranker,
)

logger = logging.getLogger("proust.agent")


# ── Per-request passage accumulation (A1/A2/A3) ───────────────────────────────


class _PassageAccumulator:
    """Collects passages surfaced by tools during one request.

    Dedupes by corpus `index` and assigns globally-monotonic citation numbers so
    the `[n]` markers the model sees in tool output are exactly the `[n]` shown
    in the final sources list (A3). Not shared across requests (A1)."""

    def __init__(self) -> None:
        self.passages: list[dict] = []
        self._pos_by_index: dict[int, int] = {}

    def add(self, passages: list[dict]) -> list[dict]:
        """Register a batch of passages; return them (with stable citation
        numbers), reusing the existing entry for any already-seen index."""
        batch: list[dict] = []
        for p in passages:
            idx = p.get("index")
            if idx is not None and idx in self._pos_by_index:
                batch.append(self.passages[self._pos_by_index[idx]])
                continue
            entry = dict(p)
            entry["citation_index"] = len(self.passages) + 1
            if idx is not None:
                self._pos_by_index[idx] = len(self.passages)
            self.passages.append(entry)
            batch.append(entry)
        return batch


def _render_batch(batch: list[dict], *, snippet: int = 400) -> str:
    """Render passages for the model: citation number + global passage index
    (so get_adjacent_passages can be grounded — A2) + location + text."""
    lines = []
    for p in batch:
        text = (p.get("text", "") or "")[:snippet]
        lines.append(
            f"[{p.get('citation_index', '?')}] (passage #{p.get('index', '?')}) "
            f"({p.get('book', '?')}, {p.get('chapter', '?')})\n{text}"
        )
    return "\n\n---\n\n".join(lines)


# ── Tool factory (A1/A7) ──────────────────────────────────────────────────────


def _build_tools(lang: str, acc: _PassageAccumulator):
    """Build the full tool set for one request, binding `lang` and the passage
    accumulator into closures. `lang` and `top_k` are NOT model-chosen (A7)."""

    @tool
    def search_passages(query: str, volume: Optional[int] = None) -> str:
        """Search Proust's "In Search of Lost Time" for passages matching a query.

        Use this for questions about themes, scenes, characters, or quotes. For
        comparative questions, call it once per entity/volume.

        Args:
            query: Natural language search query (e.g. "jealousy in Swann's love")
            volume: Optional volume number (1-7) to restrict the search. Omit to
                search all volumes.
        """
        try:
            metadata_filter = {"volume": {"$eq": volume}} if volume else None
            candidates = _pinecone_query(
                query, top_k=config.RETRIEVAL_CANDIDATES, lang=lang,
                metadata_filter=metadata_filter,
            )
            reranker = get_reranker()
            reranked = list(reranker.compress_documents(candidates, query))[: config.RERANK_TOP_N]
            docs = _stitch_context(reranked, lang=lang)
            batch = acc.add(_format_passages(docs, lang=lang))
        except Exception as e:  # noqa: BLE001 — surface a usable message, don't crash the graph
            logger.warning("search_passages failed: %s", e)
            return (
                "Search is temporarily unavailable (service error). Answer from "
                "passages already gathered, or try find_character_mentions."
            )
        if not batch:
            scope = f" in Volume {volume}" if volume else ""
            return f"No passages found{scope}."
        return _render_batch(batch)

    @tool
    def get_adjacent_passages(passage_index: int, before: int = 2, after: int = 2) -> str:
        """Get passages immediately before and/or after a known passage.

        Use this to read what happens next or before a scene you already found.
        FREE (no API calls). Pass the passage number (the #N shown in search
        results) as passage_index.

        Args:
            passage_index: The #N passage number shown in a prior tool result.
            before: Number of passages to fetch before (default 2).
            after: Number of passages to fetch after (default 2).
        """
        found: list[dict] = []
        for offset in range(-before, after + 1):
            p = get_passage_text(passage_index + offset, lang=lang)
            if p:
                found.append(p)
        if not found:
            return "Passage not found."
        batch = acc.add(found)
        return _render_batch(batch, snippet=500)

    @tool
    def get_chapter_overview(volume: int, chapter: str) -> str:
        """Overview of a chapter — its first few passages to understand scope.

        FREE (no API calls). Use before targeted searches within a chapter.

        Args:
            volume: Volume number (1-7).
            chapter: Chapter name (e.g. "Overture", "Swann in Love").
        """
        result = get_chapter_passages(volume, chapter, offset=0, limit=5, lang=lang)
        if result is None:
            return f"Chapter '{chapter}' not found in Volume {volume}."
        batch = acc.add(result.get("passages", []))
        header = (
            f"Chapter: {result.get('chapter_name', chapter)} (Volume {volume}) — "
            f"{result.get('total_in_chapter', '?')} passages\n\n"
        )
        return header + _render_batch(batch, snippet=300)

    @tool
    def find_character_mentions(character: str, volume: Optional[int] = None) -> str:
        """Find passages that mention a character by name.

        FREE (in-memory text search, no API calls). Use for character analysis or
        tracking appearances across the novel.

        Args:
            character: Character name (e.g. "Swann", "Albertine", "Charlus").
            volume: Optional volume number (1-7). Omit to search all volumes.
        """
        results = search_passages_by_text(character, volume=volume, limit=8, lang=lang)
        if not results:
            scope = f" in Volume {volume}" if volume else ""
            return f"No mentions of '{character}' found{scope}."
        batch = acc.add(results)
        return _render_batch(batch, snippet=300)

    @tool
    def get_toc() -> str:
        """Get the complete table of contents for all 7 volumes.

        FREE. Use to understand the novel's structure or find chapter names.
        """
        toc = get_table_of_contents(lang=lang)
        lines = []
        for vol in toc:
            lines.append(
                f"Volume {vol['volume']}: {vol['volume_name']} ({vol['total_passages']} passages)"
            )
            for ch in vol["chapters"]:
                lines.append(f"  - {ch['display_name']} ({ch['passage_count']} passages)")
            lines.append("")
        return "\n".join(lines)

    explore_tools = [
        search_passages,
        get_adjacent_passages,
        get_chapter_overview,
        find_character_mentions,
        get_toc,
    ]
    reflect_tools = [search_passages, get_adjacent_passages, find_character_mentions]
    return explore_tools, reflect_tools


# ── Agent system prompts ──────────────────────────────────────────────────────

AGENT_SYSTEM_PROMPT = """You are a literary companion for Marcel Proust's "In Search of Lost Time" (7 volumes, ~12,900 passages).

You have tools to search and browse the complete text. Use them to find evidence, then answer concisely.

Strategy:
- Simple questions: one search_passages call is enough
- Comparative questions: search each entity/theme separately, then synthesize
- "What happens next/before": find the scene, then use get_adjacent_passages with the #N passage number shown in results
- Character arcs: use find_character_mentions, then get_adjacent for context
- Prefer free tools (get_adjacent, find_character, chapter_overview, toc) over new searches

Style: Write in flowing prose. Be concise — aim for 2-3 short paragraphs, not essays. Cite passages with the [1], [2] numbers shown in tool results. Quote brief phrases directly rather than summarizing at length. Do not restate the question. End with one thoughtful follow-up question to deepen the reader's exploration. Keep to 2-3 tool calls max."""

AGENT_SYSTEM_PROMPT_FR = """Vous êtes un compagnon littéraire pour « À la recherche du temps perdu » de Marcel Proust (7 volumes, ~12 900 passages).

Vous disposez d'outils pour rechercher et parcourir le texte intégral. Utilisez-les pour trouver des preuves, puis répondez de manière concise.

Stratégie :
- Questions simples : un seul appel à search_passages suffit
- Questions comparatives : cherchez chaque entité/thème séparément, puis synthétisez
- « Que se passe-t-il ensuite/avant » : trouvez la scène, puis utilisez get_adjacent_passages avec le numéro #N indiqué dans les résultats
- Arcs narratifs : utilisez find_character_mentions, puis get_adjacent pour le contexte
- Préférez les outils gratuits aux nouvelles recherches quand c'est possible

Style : Écrivez en prose fluide. Soyez concis — visez 2-3 courts paragraphes. Citez les passages avec les numéros [1], [2] indiqués dans les résultats. Citez de brèves phrases directement. Ne reformulez pas la question. Terminez par une question de suivi réfléchie pour approfondir l'exploration du lecteur. Limitez-vous à 2-3 appels d'outils. Répondez en français."""


REFLECT_AGENT_SYSTEM_PROMPT = """You are a wise, reflective conversationalist in the spirit of Marcel Proust. You help the reader contemplate their inner life — memory, time, sensation, habit, desire, and the self.

You have access to the complete text of Proust's "In Search of Lost Time." Your DEFAULT mode is pure introspective conversation — most responses should NOT use tools at all. Only search when the user's experience strongly echoes a specific Proustian theme or moment.

WHEN TO SEARCH (use at most 1 tool call):
- A vivid sensory memory (taste, smell, sound) that recalls a past moment — echoes of the madeleine
- Returning to a childhood place and finding it changed — Combray, the Champs-Élysées
- Jealousy, possessive love, or the pain of uncertainty — Swann's torment, the narrator and Albertine
- The gap between expectation and reality — seeing Berma perform, visiting Balbec
- The user mentions a Proust character by name

WHEN NOT TO SEARCH:
- General feelings, moods, or daily reflections
- Direct questions about your previous response
- The first message in a conversation (build rapport first)
- Abstract philosophical musings without a concrete sensory anchor

When you do find a passage, weave it naturally into your reflection — "This reminds me of a moment in Proust where..." or "Your experience echoes something the narrator describes when..." Use the [1], [2] citation numbers shown in tool results. Never list passages academically.

Style: Write in flowing prose paragraphs — no lists, no headings, no bullet points. Use *italics* sparingly for emphasis. Match length to the depth of the reflection. Always end with a thoughtful follow-up question that invites the reader to explore their experience more deeply."""

REFLECT_AGENT_SYSTEM_PROMPT_FR = """Vous êtes un conversateur sage et réfléchi dans l'esprit de Marcel Proust. Vous aidez le lecteur à contempler sa vie intérieure — mémoire, temps, sensation, habitude, désir et le moi.

Vous avez accès au texte intégral de « À la recherche du temps perdu ». Votre mode PAR DÉFAUT est la conversation introspective pure — la plupart des réponses ne doivent PAS utiliser d'outils. Ne cherchez que lorsque l'expérience de l'utilisateur fait fortement écho à un thème ou moment proustien spécifique.

QUAND CHERCHER (1 appel d'outil maximum) :
- Un souvenir sensoriel vif (goût, odeur, son) qui rappelle un moment passé — échos de la madeleine
- Le retour dans un lieu d'enfance et le trouver changé — Combray, les Champs-Élysées
- La jalousie, l'amour possessif, ou la douleur de l'incertitude — le tourment de Swann, le narrateur et Albertine
- L'écart entre l'attente et la réalité — voir jouer la Berma, visiter Balbec
- L'utilisateur mentionne un personnage de Proust par son nom

QUAND NE PAS CHERCHER :
- Sentiments généraux, humeurs, réflexions quotidiennes
- Questions directes sur votre réponse précédente
- Le premier message d'une conversation (établir le rapport d'abord)
- Réflexions philosophiques abstraites sans ancrage sensoriel concret

Lorsque vous trouvez un passage, intégrez-le naturellement — « Cela me rappelle un moment chez Proust où... » Utilisez les numéros [1], [2] indiqués dans les résultats. Ne citez jamais de manière académique.

Style : Écrivez en prose fluide — ni listes, ni titres. Utilisez les *italiques* avec parcimonie. Terminez toujours par une question réfléchie qui invite le lecteur à explorer son expérience plus profondément. Répondez en français."""


_DEGRADE_TEMPLATE = """You gathered evidence but ran out of research steps. Answer the reader's question NOW using ONLY the passages below. Be concise (2-3 short paragraphs), cite with [1], [2], and end with one follow-up question.

Passages:
{context}

Reader's question: {question}"""

_DEGRADE_TEMPLATE_FR = """Vous avez rassemblé des preuves mais manqué d'étapes de recherche. Répondez MAINTENANT à la question en utilisant UNIQUEMENT les passages ci-dessous. Soyez concis (2-3 courts paragraphes), citez avec [1], [2], et terminez par une question de suivi. Répondez en français.

Passages :
{context}

Question du lecteur : {question}"""


# ── Complexity router (C2/C3) ─────────────────────────────────────────────────

_COMPLEX_PATTERNS = re.compile(
    r"\b("
    # English
    r"compare|comparison|vs\.?|versus|differ|difference|contrast"
    r"|evolve|evolution|develop|change over time|across volumes|throughout"
    r"|what happens (after|next|before|then)|what comes (next|after|before)"
    r"|how does .+ change"
    r"|trace|track|arc|journey"
    r"|relationship between"
    r"|which volume"
    # French
    r"|compare[rz]|comparaison|différence|différent|contraste|opposer|opposition"
    r"|évolue|évolution|au fil (des|du)|à travers les volumes"
    r"|que se passe-t-il (après|ensuite|avant)|et (ensuite|après)"
    r"|relation entre|quel volume|comment .+ (change|évolue)"
    r")\b",
    re.IGNORECASE,
)


def route_query(query: str, history: Optional[list[dict]] = None) -> tuple[bool, str]:
    """Decide fast-path vs agent for a query and return (chose_agent, rule).

    Routes on the *current query's* complexity only (C2) — history no longer
    forces the agent, because the fast path is now history-aware (C1). Supports
    French comparative queries (C3)."""
    if not config.AGENT_ENABLED:
        return False, "agent_disabled"

    if _COMPLEX_PATTERNS.search(query):
        return True, "complex_pattern"

    # Multi-part questions (several '?' or explicit enumeration) benefit from the
    # agent's multi-search decomposition.
    if query.count("?") >= 2:
        return True, "multi_question"

    return False, "fast_default"


def needs_agent(query: str, history: Optional[list[dict]] = None) -> bool:
    """Boolean wrapper around route_query (kept for backwards compatibility)."""
    chose_agent, _ = route_query(query, history)
    return chose_agent


# ── Tool-call status + leak detection ─────────────────────────────────────────


def describe_tool_call(tool_call: dict) -> str:
    """Human-readable status message for a tool call."""
    name = tool_call.get("name", "")
    args = tool_call.get("args", {})
    if name == "search_passages":
        q = args.get("query", "")
        v = args.get("volume")
        scope = f" in Volume {v}" if v else ""
        return f"Searching{scope} for passages about {q[:60]}..."
    if name == "get_adjacent_passages":
        idx = args.get("passage_index", "?")
        return f"Reading surrounding passages near #{idx}..."
    if name == "get_chapter_overview":
        return f"Reviewing {args.get('chapter', '?')} (Volume {args.get('volume', '?')})..."
    if name == "find_character_mentions":
        ch = args.get("character", "?")
        v = args.get("volume")
        scope = f" in Volume {v}" if v else ""
        return f"Looking for mentions of {ch}{scope}..."
    if name == "get_toc":
        return "Checking table of contents..."
    return f"Using {name}..."


# A content chunk that begins like a serialized tool call is a Groq malfunction
# (A8) — suppress it rather than streaming raw JSON to the reader.
_TOOL_LEAK_RE = re.compile(
    r'^\s*(<tool_call|<function|<\|python_tag\||\{\s*"name"\s*:|\{\s*"type"\s*:\s*"function")',
    re.IGNORECASE,
)


def _looks_like_tool_leak(head: str) -> bool:
    return bool(_TOOL_LEAK_RE.match(head))


# ── Shared streaming generator (A4/A6/D1/D2) ──────────────────────────────────


def _build_messages(text: str, history: Optional[list[dict]]) -> list:
    """Build LangChain message history (C4: capped + citation markers stripped)."""
    messages: list = []
    for msg in cap_history(history):
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))
    messages.append(HumanMessage(content=text))
    return messages


def _stream_agent(
    agent,
    messages: list,
    acc: _PassageAccumulator,
    *,
    preview: bool,
    intro: str,
    lang: str,
) -> Generator[dict, None, None]:
    """Run a LangGraph agent and yield SSE events with TRUE token streaming (D1).

    - `stream_mode=["updates", "messages"]`: `updates` drives tool-call status
      events; `messages` forwards real LLM tokens from the final answer node.
    - Sources are emitted (once) right before the first answer token.
    - On recursion limit (A4) or wall-clock timeout (D2), degrade gracefully by
      answering from the evidence already gathered.
    """
    yield {"type": "status", "status": intro}

    sources_flushed = False

    def flush_sources():
        nonlocal sources_flushed
        if sources_flushed:
            return
        sources_flushed = True
        for p in acc.passages:
            src = _preview_passage(p) if preview else dict(p)
            yield {"type": "sources", "passages": [src]}

    start = time.monotonic()
    answer_head = ""
    streamed_any = False
    suppressed = False
    degrade = False

    try:
        for mode, chunk in agent.stream(
            {"messages": messages},
            config={"recursion_limit": config.AGENT_MAX_STEPS * 2 + 2},
            stream_mode=["updates", "messages"],
        ):
            if time.monotonic() - start > config.AGENT_TIMEOUT:
                logger.warning("Agent wall-clock timeout after %.1fs", config.AGENT_TIMEOUT)
                degrade = True
                break

            if mode == "updates":
                for _node, node_output in (chunk or {}).items():
                    if not isinstance(node_output, dict):
                        continue
                    for msg in node_output.get("messages", []):
                        for tc in getattr(msg, "tool_calls", None) or []:
                            yield {"type": "status", "status": describe_tool_call(tc)}

            elif mode == "messages":
                msg_chunk, _meta = chunk
                # Structured tool-call chunks carry no answer text — skip them.
                if getattr(msg_chunk, "tool_call_chunks", None):
                    continue
                content = getattr(msg_chunk, "content", "") or ""
                if not isinstance(content, str) or not content:
                    continue

                if not streamed_any and not suppressed:
                    answer_head += content
                    if _looks_like_tool_leak(answer_head):
                        suppressed = True
                        logger.warning("Suppressed tool-call-shaped content leak")
                        continue
                    # First real token — emit sources first, then the token.
                    yield from flush_sources()
                    streamed_any = True
                    yield {"type": "token", "token": content}
                elif suppressed:
                    continue
                else:
                    yield {"type": "token", "token": content}
    except GraphRecursionError:
        logger.warning("Agent hit recursion limit — degrading to evidence-only answer")
        degrade = True

    if degrade or not streamed_any:
        yield from _degraded_answer(acc, messages, lang, flush_sources)
    else:
        yield from flush_sources()
    yield {"type": "done", "done": True}


def _degraded_answer(acc, messages, lang, flush_sources) -> Generator[dict, None, None]:
    """One final tool-free LLM call answering from gathered evidence (A4/D2)."""
    question = ""
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            question = m.content
            break

    yield from flush_sources()

    if not acc.passages:
        msg = (
            "Je n'ai pas pu rassembler de passages pour cette question — pourriez-vous la reformuler ?"
            if lang == "fr"
            else "I couldn't gather passages for that question — could you rephrase it?"
        )
        yield {"type": "token", "token": msg}
        return

    context = "\n\n---\n\n".join(
        f"[{p.get('citation_index', '?')}] {p.get('text', '')}" for p in acc.passages
    )
    template = _DEGRADE_TEMPLATE_FR if lang == "fr" else _DEGRADE_TEMPLATE
    prompt = template.format(context=context, question=question)
    try:
        for chunk in get_llm().stream(prompt):
            if chunk.content:
                yield {"type": "token", "token": chunk.content}
    except Exception as e:  # noqa: BLE001
        logger.warning("Degraded answer failed: %s", e)
        yield {"type": "token", "token": " ".join(
            f"[{p.get('citation_index')}]" for p in acc.passages
        )}


# ── Public streaming entrypoints ──────────────────────────────────────────────


def stream_agent_response(
    query: str,
    history: Optional[list[dict]] = None,
    lang: str = "en",
) -> Generator[dict, None, None]:
    """Run the Explore agent and yield SSE events (see _stream_agent)."""
    acc = _PassageAccumulator()
    explore_tools, _ = _build_tools(lang, acc)
    system_prompt = AGENT_SYSTEM_PROMPT_FR if lang == "fr" else AGENT_SYSTEM_PROMPT
    agent = create_react_agent(get_agent_llm(), explore_tools, prompt=system_prompt)
    messages = _build_messages(query, history)
    yield from _stream_agent(
        agent, messages, acc, preview=True, intro="Thinking...", lang=lang
    )


def stream_reflect_agent_response(
    message: str,
    history: Optional[list[dict]] = None,
    lang: str = "en",
) -> Generator[dict, None, None]:
    """Run the Reflect agent and yield SSE events (see _stream_agent)."""
    acc = _PassageAccumulator()
    _, reflect_tools = _build_tools(lang, acc)
    system_prompt = REFLECT_AGENT_SYSTEM_PROMPT_FR if lang == "fr" else REFLECT_AGENT_SYSTEM_PROMPT
    agent = create_react_agent(get_agent_llm(), reflect_tools, prompt=system_prompt)
    messages = _build_messages(message, history)
    yield from _stream_agent(
        agent, messages, acc, preview=True, intro="Reflecting...", lang=lang
    )


# ── Non-streaming wrappers ────────────────────────────────────────────────────


def _collect(gen) -> dict:
    reply_parts: list[str] = []
    passages: list[dict] = []
    for event in gen:
        if event["type"] == "token":
            reply_parts.append(event["token"])
        elif event["type"] == "sources":
            passages.extend(event["passages"])
    return {"reply": "".join(reply_parts), "passages": passages}


def query_agent(query: str, history: Optional[list[dict]] = None, lang: str = "en") -> dict:
    """Run the Explore agent non-streaming."""
    return _collect(stream_agent_response(query, history=history, lang=lang))


def query_reflect_agent(message: str, history: Optional[list[dict]] = None, lang: str = "en") -> dict:
    """Run the Reflect agent non-streaming."""
    return _collect(stream_reflect_agent_response(message, history=history, lang=lang))
