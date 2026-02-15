"""
LangGraph ReAct agent for ProustGPT.

Provides a tool-calling agent that can decompose complex literary questions
into multiple targeted searches across the Proust corpus, with conversation
memory for follow-up questions.
"""
import re
from contextvars import ContextVar
from typing import Generator

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool
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
    _detect_repetition,
    get_llm,
    get_reranker,
)


# ── Thread-safe passage accumulation ─────────────────────────────────────────
# Each request gets its own list via contextvars, safe for concurrent use.
_tool_passages_var: ContextVar[list[dict]] = ContextVar("tool_passages", default=[])


# ── Tool definitions ─────────────────────────────────────────────────────────


@tool
def search_passages(query: str, top_k: int = 5, lang: str = "en") -> str:
    """Search the complete text of Proust's 'In Search of Lost Time' for passages matching a query.

    Use this for general questions about themes, scenes, characters, or quotes.
    Returns the top matching passages with volume/chapter info.

    Args:
        query: Natural language search query (e.g. "jealousy in Swann's love")
        top_k: Number of passages to return (default 5, max 8)
        lang: Language for results — "en" for English, "fr" for French
    """
    top_k = min(top_k, 8)
    candidates = _pinecone_query(query, top_k=20, lang=lang)
    reranker = get_reranker()
    reranked = list(reranker.compress_documents(candidates, query))[:top_k]
    docs = _stitch_context(reranked, lang=lang)
    passages = _format_passages(docs, lang=lang)

    _tool_passages_var.get().extend(passages)

    lines = []
    for i, p in enumerate(passages):
        text = p.get("text", "")[:400]
        lines.append(
            f"[{p.get('citation_index', i+1)}] ({p.get('book', '?')}, {p.get('chapter', '?')}) "
            f"{text}"
        )
    return "\n\n".join(lines) if lines else "No passages found."


@tool
def search_by_volume(query: str, volume: int, top_k: int = 5, lang: str = "en") -> str:
    """Search for passages within a specific volume of Proust's novel.

    Use this when the question targets a particular volume, or when doing
    comparative analysis across volumes (call once per volume).

    Args:
        query: Natural language search query
        volume: Volume number (1-7)
        top_k: Number of passages to return (default 5, max 8)
        lang: Language for results — "en" or "fr"
    """
    top_k = min(top_k, 8)
    metadata_filter = {"volume": {"$eq": volume}}
    candidates = _pinecone_query(query, top_k=20, lang=lang, metadata_filter=metadata_filter)
    reranker = get_reranker()
    reranked = list(reranker.compress_documents(candidates, query))[:top_k]
    docs = _stitch_context(reranked, lang=lang)
    passages = _format_passages(docs, lang=lang)

    _tool_passages_var.get().extend(passages)

    lines = []
    for i, p in enumerate(passages):
        text = p.get("text", "")[:400]
        lines.append(
            f"[{p.get('citation_index', i+1)}] ({p.get('book', '?')}, {p.get('chapter', '?')}) "
            f"{text}"
        )
    return "\n\n".join(lines) if lines else f"No passages found in Volume {volume}."


@tool
def get_adjacent_passages(passage_index: int, before: int = 2, after: int = 2, lang: str = "en") -> str:
    """Get passages immediately before and/or after a known passage.

    Use this to read what happens next or before a scene you've already found.
    This is a FREE operation (no API calls) — prefer it over new searches when
    you already know the passage location.

    Args:
        passage_index: The index of the known passage
        before: Number of passages to fetch before (default 2)
        after: Number of passages to fetch after (default 2)
        lang: Language — "en" or "fr"
    """
    results = []
    for offset in range(-before, after + 1):
        idx = passage_index + offset
        p = get_passage_text(idx, lang=lang)
        if p:
            marker = " <<< [anchor]" if offset == 0 else ""
            results.append(f"[passage {idx}]{marker} ({p.get('book', '?')}, {p.get('chapter', '?')})\n{p.get('text', '')[:500]}")
    return "\n\n---\n\n".join(results) if results else "Passage not found."


@tool
def get_chapter_overview(volume: int, chapter: str, lang: str = "en") -> str:
    """Get an overview of a specific chapter — first few passages to understand what it covers.

    This is a FREE operation (no API calls). Use it to understand the scope of a
    chapter before doing targeted searches within it.

    Args:
        volume: Volume number (1-7)
        chapter: Chapter name (e.g. "Overture", "Swann in Love")
        lang: Language — "en" or "fr"
    """
    result = get_chapter_passages(volume, chapter, offset=0, limit=5, lang=lang)
    if result is None:
        return f"Chapter '{chapter}' not found in Volume {volume}."

    lines = [f"Chapter: {result.get('chapter_name', chapter)} (Volume {volume})"]
    lines.append(f"Total passages: {result.get('total_in_chapter', '?')}")
    lines.append("")
    for p in result.get("passages", []):
        lines.append(f"[passage {p.get('index', '?')}] {p.get('text', '')[:300]}")
        lines.append("")
    return "\n".join(lines)


@tool
def find_character_mentions(character: str, volume: int | None = None, lang: str = "en") -> str:
    """Find passages that mention a specific character by name.

    This is a FREE operation (in-memory text search, no API calls). Use it for
    character analysis, tracking character appearances across the novel.

    Args:
        character: Character name to search for (e.g. "Swann", "Albertine", "Charlus")
        volume: Optional volume number to limit search (1-7). Omit to search all volumes.
        lang: Language — "en" or "fr"
    """
    results = search_passages_by_text(character, volume=volume, limit=8, lang=lang)
    if not results:
        scope = f" in Volume {volume}" if volume else ""
        return f"No mentions of '{character}' found{scope}."

    lines = []
    for p in results:
        lines.append(
            f"[passage {p.get('index', '?')}] ({p.get('book', '?')}, {p.get('chapter', '?')})\n"
            f"{p.get('text', '')[:300]}"
        )
    return "\n\n---\n\n".join(lines)


@tool
def get_toc(lang: str = "en") -> str:
    """Get the complete table of contents for all 7 volumes.

    This is a FREE operation. Use it to understand the novel's structure,
    find chapter names, or help the user navigate.

    Args:
        lang: Language for volume/chapter names — "en" or "fr"
    """
    toc = get_table_of_contents(lang=lang)
    lines = []
    for vol in toc:
        lines.append(f"Volume {vol['volume']}: {vol['volume_name']} ({vol['total_passages']} passages)")
        for ch in vol["chapters"]:
            lines.append(f"  - {ch['display_name']} ({ch['passage_count']} passages)")
        lines.append("")
    return "\n".join(lines)


# ── Agent system prompt ──────────────────────────────────────────────────────

AGENT_SYSTEM_PROMPT = """You are a literary companion for Marcel Proust's "In Search of Lost Time" (7 volumes, ~12,900 passages).

You have tools to search and browse the complete text. Use them to find evidence, then answer concisely.

Strategy:
- Simple questions: one search_passages call is enough
- Comparative questions: search each entity/theme separately, then synthesize
- "What happens next/before": find the scene, then use get_adjacent_passages
- Character arcs: use find_character_mentions, then get_adjacent for context
- Prefer free tools (get_adjacent, find_character, chapter_overview, toc) over search

Style: Write in flowing prose. Be concise — aim for 2-3 short paragraphs, not essays. Cite passages with [1], [2], etc. Quote brief phrases directly rather than summarizing at length. Do not restate the question. Keep to 2-3 tool calls max."""

AGENT_SYSTEM_PROMPT_FR = """Vous êtes un compagnon littéraire pour « À la recherche du temps perdu » de Marcel Proust (7 volumes, ~12 900 passages).

Vous disposez d'outils pour rechercher et parcourir le texte intégral. Utilisez-les pour trouver des preuves, puis répondez de manière concise.

Stratégie :
- Questions simples : un seul appel à search_passages suffit
- Questions comparatives : cherchez chaque entité/thème séparément, puis synthétisez
- « Que se passe-t-il ensuite/avant » : trouvez la scène, puis utilisez get_adjacent_passages
- Arcs narratifs : utilisez find_character_mentions, puis get_adjacent pour le contexte
- Préférez les outils gratuits aux recherches quand c'est possible

Style : Écrivez en prose fluide. Soyez concis — visez 2-3 courts paragraphes. Citez les passages avec [1], [2], etc. Citez de brèves phrases directement. Ne reformulez pas la question. Limitez-vous à 2-3 appels d'outils. Répondez en français."""


# ── Reflect agent system prompts ─────────────────────────────────────────

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

When you do find a passage, weave it naturally into your reflection — "This reminds me of a moment in Proust where..." or "Your experience echoes something the narrator describes when..." Use [1], [2] citation markers. Never list passages academically.

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

Lorsque vous trouvez un passage, intégrez-le naturellement — « Cela me rappelle un moment chez Proust où... » Utilisez les marqueurs [1], [2]. Ne citez jamais de manière académique.

Style : Écrivez en prose fluide — ni listes, ni titres. Utilisez les *italiques* avec parcimonie. Terminez toujours par une question réfléchie qui invite le lecteur à explorer son expérience plus profondément. Répondez en français."""


# ── Agent factory ────────────────────────────────────────────────────────────

_TOOLS = [
    search_passages,
    search_by_volume,
    get_adjacent_passages,
    get_chapter_overview,
    find_character_mentions,
    get_toc,
]


def create_proust_agent(lang: str = "en"):
    """Create and return a LangGraph ReAct agent configured for Proust exploration."""
    llm = get_llm()
    system_prompt = AGENT_SYSTEM_PROMPT_FR if lang == "fr" else AGENT_SYSTEM_PROMPT
    agent = create_react_agent(llm, _TOOLS, prompt=system_prompt)
    return agent


_REFLECT_TOOLS = [
    search_passages,
    get_adjacent_passages,
    find_character_mentions,
]


def create_reflect_agent(lang: str = "en"):
    """Create and return a LangGraph ReAct agent configured for Proustian reflection."""
    llm = get_llm()
    system_prompt = REFLECT_AGENT_SYSTEM_PROMPT_FR if lang == "fr" else REFLECT_AGENT_SYSTEM_PROMPT
    agent = create_react_agent(llm, _REFLECT_TOOLS, prompt=system_prompt)
    return agent


# ── Complexity router ────────────────────────────────────────────────────────

_COMPLEX_PATTERNS = re.compile(
    r"\b("
    r"compare|comparison|vs\.?|versus|differ|difference|contrast"
    r"|evolve|evolution|develop|change over time|across volumes"
    r"|what happens (after|next|before|then)"
    r"|how does .+ change"
    r"|trace|track|arc|journey"
    r"|relationship between"
    r")\b",
    re.IGNORECASE,
)


def needs_agent(query: str, history: list[dict] | None = None) -> bool:
    """Determine whether a query needs the full agent or can use the fast path.

    Returns True for complex/comparative queries or follow-up questions.
    """
    if not config.AGENT_ENABLED:
        return False

    # Any conversation with 2+ prior user messages likely needs context
    if history:
        user_msgs = [m for m in history if m.get("role") == "user"]
        if len(user_msgs) >= 2:
            return True

    # Check for complexity patterns
    if _COMPLEX_PATTERNS.search(query):
        return True

    # Short follow-up queries (likely referencing prior context)
    if history and len(query.split()) <= 6:
        return True

    return False


# ── Streaming generator ─────────────────────────────────────────────────────

def describe_tool_call(tool_call: dict) -> str:
    """Generate a human-readable status message for a tool call."""
    name = tool_call.get("name", "")
    args = tool_call.get("args", {})

    if name == "search_passages":
        q = args.get("query", "")
        return f"Searching for passages about {q[:60]}..."
    elif name == "search_by_volume":
        q = args.get("query", "")
        v = args.get("volume", "?")
        return f"Searching Volume {v} for {q[:50]}..."
    elif name == "get_adjacent_passages":
        idx = args.get("passage_index", "?")
        return f"Reading surrounding passages near #{idx}..."
    elif name == "get_chapter_overview":
        ch = args.get("chapter", "?")
        v = args.get("volume", "?")
        return f"Reviewing {ch} (Volume {v})..."
    elif name == "find_character_mentions":
        ch = args.get("character", "?")
        v = args.get("volume")
        scope = f" in Volume {v}" if v else ""
        return f"Looking for mentions of {ch}{scope}..."
    elif name == "get_toc":
        return "Checking table of contents..."
    return f"Using {name}..."


def stream_agent_response(
    query: str,
    history: list[dict] | None = None,
    lang: str = "en",
) -> Generator[dict, None, None]:
    """
    Run the LangGraph agent and yield SSE events.

    Yields:
        {"type": "status", "status": "..."}   — tool-call status updates
        {"type": "token", "token": "..."}      — streamed response tokens
        {"type": "sources", "passages": [...]} — accumulated passage sources
        {"type": "done", "done": True}         — stream complete
    """
    # Each request gets its own passage list (thread-safe via contextvars)
    passage_list: list[dict] = []
    _tool_passages_var.set(passage_list)

    yield {"type": "status", "status": "Thinking..."}

    # Build message history for the agent
    messages: list = []
    if history:
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
    messages.append(HumanMessage(content=query))

    agent = create_proust_agent(lang=lang)

    # Stream the agent execution
    accumulated_response = ""
    steps_taken = 0

    for event in agent.stream(
        {"messages": messages},
        config={"recursion_limit": config.AGENT_MAX_STEPS * 2 + 2},
        stream_mode="updates",
    ):
        for node_name, node_output in event.items():
            if node_name == "agent":
                agent_messages = node_output.get("messages", [])
                for msg in agent_messages:
                    # Check for tool calls
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        for tc in msg.tool_calls:
                            steps_taken += 1
                            if steps_taken > config.AGENT_MAX_STEPS:
                                break
                            status = describe_tool_call(tc)
                            yield {"type": "status", "status": status}
                    # Final text content (no tool calls)
                    elif hasattr(msg, "content") and msg.content and (
                        not hasattr(msg, "tool_calls") or not msg.tool_calls
                    ):
                        content = msg.content
                        chunk_size = 12
                        for i in range(0, len(content), chunk_size):
                            chunk = content[i:i + chunk_size]
                            accumulated_response += chunk
                            yield {"type": "token", "token": chunk}
                            if _detect_repetition(accumulated_response):
                                break

    # Deduplicate passages by index
    seen_indices: set[int] = set()
    unique_passages: list[dict] = []
    citation_idx = 1
    for p in passage_list:
        p_index = p.get("index")
        if p_index is not None and p_index in seen_indices:
            continue
        if p_index is not None:
            seen_indices.add(p_index)
        p["citation_index"] = citation_idx
        citation_idx += 1
        unique_passages.append(p)

    if unique_passages:
        yield {"type": "sources", "passages": unique_passages}
    yield {"type": "done", "done": True}


def query_agent(
    query: str,
    history: list[dict] | None = None,
    lang: str = "en",
) -> dict:
    """Run the agent non-streaming. Returns {"reply": ..., "passages": [...]}."""
    reply_parts = []
    passages = []

    for event in stream_agent_response(query, history=history, lang=lang):
        if event["type"] == "token":
            reply_parts.append(event["token"])
        elif event["type"] == "sources":
            passages = event["passages"]

    return {
        "reply": "".join(reply_parts),
        "passages": passages,
    }
