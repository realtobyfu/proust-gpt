"""
LangChain orchestration for ProustGPT.
Provides embeddings (Cohere), LLM (Groq), reranking (Cohere),
vector store (Pinecone SDK), and agentic RAG chain functionality.
"""
import json
import re
from typing import Generator, Optional

from groq import Groq
from langchain_cohere import CohereEmbeddings, CohereRerank
from langchain_groq import ChatGroq
from langchain_core.documents import Document
from pinecone import Pinecone

from config import config
from text_utils import clean_passage_text


# ── Module-level singletons (lazy loaded) ────────────────────────────────────

_embeddings: Optional[CohereEmbeddings] = None
_llm: Optional[ChatGroq] = None
_groq_client: Optional[Groq] = None
_reranker: Optional[CohereRerank] = None
_pinecone_client: Optional[Pinecone] = None
_pinecone_index = None


def get_embeddings() -> CohereEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = CohereEmbeddings(
            model=config.COHERE_EMBED_MODEL,
            cohere_api_key=config.COHERE_API_KEY,
        )
    return _embeddings


def get_llm() -> ChatGroq:
    global _llm
    if _llm is None:
        if not config.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not configured")
        _llm = ChatGroq(
            model=config.LLM_MODEL_NAME,
            api_key=config.GROQ_API_KEY,
            temperature=config.LLM_TEMPERATURE,
            max_tokens=config.LLM_MAX_TOKENS,
        )
    return _llm


def get_groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        if not config.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not configured")
        _groq_client = Groq(api_key=config.GROQ_API_KEY)
    return _groq_client


def get_reranker() -> CohereRerank:
    global _reranker
    if _reranker is None:
        _reranker = CohereRerank(
            model=config.COHERE_RERANK_MODEL,
            cohere_api_key=config.COHERE_API_KEY,
            top_n=config.RERANK_TOP_N,
        )
    return _reranker


def get_pinecone_client() -> Pinecone:
    global _pinecone_client
    if _pinecone_client is None:
        if not config.PINECONE_API_KEY:
            raise ValueError("PINECONE_API_KEY not configured")
        _pinecone_client = Pinecone(api_key=config.PINECONE_API_KEY)
    return _pinecone_client


def get_pinecone_index():
    global _pinecone_index
    if _pinecone_index is None:
        client = get_pinecone_client()
        _pinecone_index = client.Index(config.PINECONE_INDEX_NAME)
    return _pinecone_index


# ── Prompts ───────────────────────────────────────────────────────────────────

RAG_SYSTEM_PROMPT = """You are a literary companion guiding a reader through Marcel Proust's "In Search of Lost Time."
You speak in flowing, contemplative prose — never in lists, bullet points, numbered sections, or structured outlines.

RULES:
- Write in continuous prose paragraphs only. Never use bullet points, numbered lists, bold headers, or section headings.
- Calibrate your response to the question's scope: answer simple factual questions in 1-2 sentences or a short paragraph; explore complex thematic or interpretive questions in 2-3 fuller paragraphs.
- You may use *italics* for titles and brief quotations. Do not use any other formatting.
- Use the search_proust tool when the reader asks about specific content from the text.
- You do NOT need to search for every question — if it's about you, general literary knowledge, or a follow-up, respond directly.
- After searching, use cite_passages to select only the most apt 1-3 passages for the reader to see.
- Quote brief phrases from the passages when apt, weaving them into your prose naturally."""

RAG_SYSTEM_PROMPT_FR = """Vous êtes un compagnon littéraire guidant un lecteur à travers « À la recherche du temps perdu » de Marcel Proust.
Vous vous exprimez dans une prose fluide et contemplative — jamais sous forme de listes, de puces, de sections numérotées ou de plans structurés.

RÈGLES :
- Écrivez uniquement en paragraphes de prose continue. N'utilisez jamais de puces, de listes numérotées, de titres en gras ou d'en-têtes de section.
- Adaptez votre réponse à la portée de la question : répondez aux questions factuelles simples en 1-2 phrases ou un court paragraphe ; explorez les questions thématiques ou interprétatives complexes en 2-3 paragraphes plus développés.
- Vous pouvez utiliser des *italiques* pour les titres et les citations brèves. N'utilisez aucune autre mise en forme.
- Utilisez l'outil search_proust lorsque le lecteur pose des questions sur le contenu spécifique du texte.
- Vous n'avez PAS besoin de chercher pour chaque question — s'il s'agit de vous, de connaissances littéraires générales ou d'un suivi, répondez directement.
- Après la recherche, utilisez cite_passages pour sélectionner uniquement les 1-3 passages les plus pertinents à montrer au lecteur.
- Citez de brèves phrases des passages quand c'est approprié, en les intégrant naturellement dans votre prose.
- Répondez toujours en français."""

REFLECT_SYSTEM_PROMPT = """You are a wise, reflective conversationalist in the spirit of Marcel Proust. You help the reader contemplate their day and inner life, drawing on themes of memory, time, sensation, and the self.

RULES:
- Write in continuous prose only. Never use bullet points, numbered lists, bold text, or section headings.
- Calibrate your response to the question's scope: answer simple factual questions in 1-2 sentences or a short paragraph; explore complex thematic or interpretive questions in 2-3 fuller paragraphs.
- You may use *italics* sparingly for emphasis. No other formatting.
- Ask one thoughtful question to invite deeper reflection."""

REFLECT_SYSTEM_PROMPT_FR = """Vous êtes un conversateur sage et réfléchi dans l'esprit de Marcel Proust. Vous aidez le lecteur à contempler sa journée et sa vie intérieure, en vous appuyant sur les thèmes de la mémoire, du temps, de la sensation et du moi.

RÈGLES :
- Écrivez uniquement en prose continue. N'utilisez jamais de puces, de listes numérotées, de texte en gras ou d'en-têtes de section.
- Adaptez votre réponse à la portée de la question : répondez aux questions factuelles simples en 1-2 phrases ou un court paragraphe ; explorez les questions thématiques ou interprétatives complexes en 2-3 paragraphes plus développés.
- Vous pouvez utiliser des *italiques* avec parcimonie pour l'emphase. Aucune autre mise en forme.
- Posez une question réfléchie pour inviter à une réflexion plus profonde.
- Répondez toujours en français."""

# Legacy prompt template (used by direct RAG fallback)
_RAG_FALLBACK_TEMPLATE = """You are a literary companion guiding a reader through Marcel Proust's "In Search of Lost Time."
You speak in flowing, contemplative prose — never in lists, bullet points, numbered sections, or structured outlines.

RULES:
- Write in continuous prose paragraphs only. Never use bullet points, numbered lists, bold headers, or section headings.
- Calibrate your response to the question's scope: answer simple factual questions in 1-2 sentences or a short paragraph; explore complex thematic or interpretive questions in 2-3 fuller paragraphs.
- You may use *italics* for titles and brief quotations. Do not use any other formatting.
- Quote brief phrases from the passages when apt, weaving them into your prose naturally.

Context passages:
{context}

Reader's question: {question}"""

_RAG_FALLBACK_TEMPLATE_FR = """Vous êtes un compagnon littéraire guidant un lecteur à travers « À la recherche du temps perdu » de Marcel Proust.
Vous vous exprimez dans une prose fluide et contemplative — jamais sous forme de listes, de puces, de sections numérotées ou de plans structurés.

RÈGLES :
- Écrivez uniquement en paragraphes de prose continue. N'utilisez jamais de puces, de listes numérotées, de titres en gras ou d'en-têtes de section.
- Adaptez votre réponse à la portée de la question : répondez aux questions factuelles simples en 1-2 phrases ou un court paragraphe ; explorez les questions thématiques ou interprétatives complexes en 2-3 paragraphes plus développés.
- Vous pouvez utiliser des *italiques* pour les titres et les citations brèves. N'utilisez aucune autre mise en forme.
- Citez de brèves phrases des passages quand c'est approprié, en les intégrant naturellement dans votre prose.
- Répondez toujours en français.

Passages de contexte :
{context}

Question du lecteur : {question}"""


def _get_rag_prompt(lang: str = "en") -> str:
    return RAG_SYSTEM_PROMPT_FR if lang == "fr" else RAG_SYSTEM_PROMPT


def _get_reflect_prompt(lang: str = "en") -> str:
    return REFLECT_SYSTEM_PROMPT_FR if lang == "fr" else REFLECT_SYSTEM_PROMPT


def _get_rag_fallback_template(lang: str = "en") -> str:
    return _RAG_FALLBACK_TEMPLATE_FR if lang == "fr" else _RAG_FALLBACK_TEMPLATE


# ── Tool definitions for agentic RAG ──────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_proust",
            "description": (
                "Search Proust's 'In Search of Lost Time' for relevant passages. "
                "Use this when the reader asks about specific scenes, characters, "
                "themes, or quotes from the text."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to find relevant passages",
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "Number of passages to retrieve (1-10)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cite_passages",
            "description": (
                "Select which retrieved passages to display to the reader. "
                "Call this with the indices of the most relevant passages "
                "that support your response. For each cited passage, explain "
                "in one sentence why it is relevant. Also provide a brief "
                "thematic synthesis connecting the passages."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "passage_indices": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Indices of passages to show (0-based, from search results)",
                    },
                    "relevance_reasons": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "One sentence per cited passage explaining why it is relevant to the reader's question",
                    },
                    "synthesis": {
                        "type": "string",
                        "description": "1-2 sentence thematic connection across the cited passages",
                    },
                },
                "required": ["passage_indices", "relevance_reasons", "synthesis"],
            },
        },
    },
]


# ── Retrieval helpers ─────────────────────────────────────────────────────────

def _pinecone_query(query: str, top_k: int) -> list[Document]:
    embeddings = get_embeddings()
    query_vector = embeddings.embed_query(query)

    index = get_pinecone_index()
    results = index.query(
        vector=query_vector,
        top_k=top_k,
        include_metadata=True,
    )

    docs = []
    for match in results.matches:
        metadata = match.metadata or {}
        text = metadata.pop("text", "")
        docs.append(Document(page_content=text, metadata=metadata))
    return docs


# ── Context stitching ─────────────────────────────────────────────────────────

def _starts_mid_sentence(text: str) -> bool:
    stripped = text.lstrip()
    if not stripped:
        return False
    # Also treat leading "..." as mid-sentence continuation
    cleaned = re.sub(r'^[.\u2026]+\s*', '', stripped)
    if not cleaned:
        return False
    return cleaned[0].islower() or stripped.startswith('...') or stripped.startswith('\u2026')


def _ends_mid_sentence(text: str) -> bool:
    stripped = text.rstrip()
    if not stripped:
        return False
    # Strip trailing "..." or "…" before checking — these are truncation markers
    cleaned = re.sub(r'[.\u2026]{2,}$', '', stripped).rstrip()
    if not cleaned:
        return True  # Only had ellipsis, definitely mid-sentence
    return cleaned[-1] not in '.!?"\u201d\u2019'


def _last_n_sentences(text: str, n: int = 2, max_chars: int = 400) -> str:
    """Grab the last n sentences (or up to max_chars) from text."""
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    if not parts:
        return ""
    selected = parts[-n:]
    result = " ".join(selected)
    if len(result) > max_chars:
        result = result[-max_chars:]
    return result


def _first_n_sentences(text: str, n: int = 2, max_chars: int = 400) -> str:
    """Grab the first n sentences (or up to max_chars) from text."""
    stripped = text.strip()
    parts = re.split(r'(?<=[.!?])\s+', stripped)
    if not parts:
        return ""
    selected = parts[:n]
    result = " ".join(selected)
    if len(result) > max_chars:
        result = result[:max_chars]
    return result


def _fetch_adjacent_passages(indices: set[int]) -> dict[int, str]:
    if not indices:
        return {}
    ids = [f"passage-{i}" for i in indices]
    index = get_pinecone_index()
    result = index.fetch(ids=ids)
    texts = {}
    for vec_id, vec_data in result.vectors.items():
        idx = int(vec_id.replace("passage-", ""))
        texts[idx] = vec_data.metadata.get("text", "")
    return texts


def _stitch_context(docs: list[Document]) -> list[Document]:
    needed: set[int] = set()
    for doc in docs:
        idx = doc.metadata.get("index")
        if idx is None:
            continue
        if _starts_mid_sentence(doc.page_content) and idx > 1:
            needed.add(idx - 1)
        if _ends_mid_sentence(doc.page_content):
            needed.add(idx + 1)

    adjacent = _fetch_adjacent_passages(needed)

    stitched = []
    for doc in docs:
        idx = doc.metadata.get("index")
        text = doc.page_content

        if idx is not None:
            if _starts_mid_sentence(text) and (idx - 1) in adjacent:
                prev_tail = _last_n_sentences(adjacent[idx - 1])
                if prev_tail:
                    text = f"...{prev_tail} {text}"

            if _ends_mid_sentence(text) and (idx + 1) in adjacent:
                next_head = _first_n_sentences(adjacent[idx + 1])
                if next_head:
                    text = f"{text} {next_head}..."

        stitched.append(Document(page_content=text, metadata=doc.metadata))

    return stitched


# ── Passage formatting ────────────────────────────────────────────────────────

def _format_passages(docs: list[Document], relevance_summaries: list[str] | None = None) -> list[dict]:
    passages = []
    for i, doc in enumerate(docs):
        p = {
            "book": doc.metadata.get("book", "Unknown"),
            "chapter": doc.metadata.get("chapter", "Unknown"),
            "text": clean_passage_text(doc.page_content),
            "volume": doc.metadata.get("volume"),
            "index": doc.metadata.get("index"),
        }
        if relevance_summaries and i < len(relevance_summaries):
            p["relevance_summary"] = relevance_summaries[i]
        passages.append(p)
    return passages


def retrieve_passages(query: str) -> list[Document]:
    candidates = _pinecone_query(query, top_k=config.RETRIEVAL_CANDIDATES)
    reranker = get_reranker()
    reranked = list(reranker.compress_documents(candidates, query))
    return _stitch_context(reranked)


# ── Tool execution ────────────────────────────────────────────────────────────

def _execute_tool(
    tool_call,
    fallback_query: str,
    all_passages: list[dict],
    cited_indices: list[int],
    cite_metadata: dict,
) -> str:
    try:
        args = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError:
        return "Error: could not parse tool arguments."

    if tool_call.function.name == "search_proust":
        search_query = args.get("query", fallback_query)
        num_results = min(max(args.get("num_results", 5), 1), 10)

        docs = retrieve_passages(search_query)
        formatted = _format_passages(docs)[:num_results]
        base_idx = len(all_passages)
        all_passages.extend(formatted)

        return json.dumps([
            {
                "index": base_idx + i,
                "book": p["book"],
                "chapter": p["chapter"],
                "text": p["text"][:500],
            }
            for i, p in enumerate(formatted)
        ])

    elif tool_call.function.name == "cite_passages":
        indices = args.get("passage_indices", [])
        cited_indices.extend(indices)
        relevance_reasons = args.get("relevance_reasons", [])
        synthesis = args.get("synthesis", "")
        cite_metadata["relevance_reasons"] = relevance_reasons
        cite_metadata["synthesis"] = synthesis
        return f"Passages at indices {indices} will be displayed to the reader."

    return "Unknown tool."


# ── Query classification ─────────────────────────────────────────────────────

# Signals that the query is about Proust's actual text and would benefit
# from passage retrieval even when the LLM chose not to search.
_PROUST_SIGNALS = re.compile(
    r"""
      proust | swann | combray | guermantes | charlus | albertine
    | odette | gilberte | françoise | madeleine | balbec | verdurin
    | narrator | involuntary\s+memory | lost\s+time | remembrance
    | temps\s+perdu | recherche | côté | jealousy\s+in | hawthorn
    | steeple | goodnight\s+kiss | petite\s+madeleine | church\s+at
    | memory\s+(?:in|and|of) | passage | scene | chapter | volume
    | quote | wrote\s+about | write\s+about | says?\s+about | text
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _query_warrants_passages(query: str) -> bool:
    """Return True if the query looks like it's about Proust's text content
    (themes, characters, scenes) rather than a meta or general question."""
    return bool(_PROUST_SIGNALS.search(query))


# ── Repetition detection ─────────────────────────────────────────────────────

def _detect_repetition(text: str, window: int = 60, threshold: int = 3) -> bool:
    """Return True if the tail of `text` contains a repeated phrase loop."""
    tail = text[-window * threshold:]
    if len(tail) < window * 2:
        return False
    # Check if the last `window` chars appear multiple times in the tail
    pattern = tail[-window:]
    count = tail.count(pattern)
    return count >= threshold


# ── Agentic RAG streaming ────────────────────────────────────────────────────

def _stream_agentic_rag(query: str, lang: str = "en") -> Generator[dict, None, None]:
    """
    Agentic RAG: the LLM decides whether to search, what to search for,
    and which passages to cite. Uses Groq tool-use API directly.
    """
    client = get_groq_client()
    all_passages: list[dict] = []
    cited_indices: list[int] = []
    cite_metadata: dict = {}

    messages = [
        {"role": "system", "content": _get_rag_prompt(lang)},
        {"role": "user", "content": query},
    ]

    max_rounds = 3
    for _ in range(max_rounds):
        resp = client.chat.completions.create(
            model=config.LLM_MODEL_NAME,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=config.LLM_TEMPERATURE,
            max_tokens=config.LLM_MAX_TOKENS,
            frequency_penalty=config.LLM_FREQUENCY_PENALTY,
        )
        msg = resp.choices[0].message

        if not msg.tool_calls:
            # Re-request with streaming for token-by-token output
            stream = client.chat.completions.create(
                model=config.LLM_MODEL_NAME,
                messages=messages,
                temperature=config.LLM_TEMPERATURE,
                max_tokens=config.LLM_MAX_TOKENS,
                frequency_penalty=config.LLM_FREQUENCY_PENALTY,
                stream=True,
            )
            accumulated = ""
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    accumulated += token
                    yield {"type": "token", "token": token}
                    if _detect_repetition(accumulated):
                        break
            break

        # Append assistant message with tool calls
        messages.append({
            "role": "assistant",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ],
        })

        # Notify frontend that retrieval is in progress
        yield {"type": "status", "status": "Searching passages..."}

        # Execute each tool call
        for tc in msg.tool_calls:
            result = _execute_tool(tc, query, all_passages, cited_indices, cite_metadata)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })
    else:
        # Exhausted all rounds — stream a final response without tools
        stream = client.chat.completions.create(
            model=config.LLM_MODEL_NAME,
            messages=messages,
            temperature=config.LLM_TEMPERATURE,
            max_tokens=config.LLM_MAX_TOKENS,
            frequency_penalty=config.LLM_FREQUENCY_PENALTY,
            stream=True,
        )
        accumulated = ""
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                token = chunk.choices[0].delta.content
                accumulated += token
                yield {"type": "token", "token": token}
                if _detect_repetition(accumulated):
                    break

    # Emit cited passages, or fallback to direct retrieval
    relevance_reasons = cite_metadata.get("relevance_reasons", [])
    synthesis = cite_metadata.get("synthesis", "")

    if cited_indices and all_passages:
        cited = [
            all_passages[i]
            for i in cited_indices
            if 0 <= i < len(all_passages)
        ]
        if not cited:
            cited = all_passages[:3]
        # Attach relevance summaries to passages
        for i, p in enumerate(cited):
            if i < len(relevance_reasons):
                p["relevance_summary"] = relevance_reasons[i]
        yield {"type": "sources", "passages": cited}
    elif all_passages:
        yield {"type": "sources", "passages": all_passages[:3]}
    else:
        # LLM didn't search — do a direct retrieval only if the query
        # seems to be about Proust's text (not a meta or general question)
        if _query_warrants_passages(query):
            try:
                docs = retrieve_passages(query)
                if docs:
                    yield {"type": "sources", "passages": _format_passages(docs)}
            except Exception:
                pass  # If retrieval fails, just skip passages

    # Emit metadata event if we have synthesis
    if synthesis:
        yield {
            "type": "metadata",
            "synthesis": synthesis,
            "passage_count": len(cited_indices),
            "query_echo": query,
        }

    yield {"type": "done", "done": True}


def _stream_direct_rag(query: str, lang: str = "en") -> Generator[dict, None, None]:
    """Fallback: direct search + generate (no tool use)."""
    docs = retrieve_passages(query)
    context = "\n\n---\n\n".join([doc.page_content for doc in docs])
    prompt = _get_rag_fallback_template(lang).format(context=context, question=query)

    llm = get_llm()
    accumulated = ""
    for chunk in llm.stream(prompt):
        if chunk.content:
            accumulated += chunk.content
            yield {"type": "token", "token": chunk.content}
            if _detect_repetition(accumulated):
                break

    yield {"type": "sources", "passages": _format_passages(docs)}
    yield {"type": "done", "done": True}


# ── Public API ────────────────────────────────────────────────────────────────

def stream_rag_response(query: str, lang: str = "en") -> Generator[dict, None, None]:
    """
    Stream a RAG response. Tries agentic tool-use flow first,
    falls back to direct retrieval if tool use fails.

    Yields:
        - {"type": "token", "token": "..."} for each token/chunk
        - {"type": "sources", "passages": [...]} for cited passages
        - {"type": "done", "done": True} when complete
    """
    try:
        yield from _stream_agentic_rag(query, lang=lang)
    except Exception as e:
        print(f"[ProustGPT] Agentic RAG failed ({e}), falling back to direct RAG")
        yield from _stream_direct_rag(query, lang=lang)


def query_rag(query: str, lang: str = "en") -> dict:
    """
    Execute a RAG query (non-streaming). Uses the same agentic flow.

    Returns:
        Dictionary with 'reply' and 'passages' keys.
    """
    reply_parts = []
    passages = []
    metadata = {}

    for event in stream_rag_response(query, lang=lang):
        if event["type"] == "token":
            reply_parts.append(event["token"])
        elif event["type"] == "sources":
            passages = event["passages"]
        elif event["type"] == "metadata":
            metadata = event

    result = {
        "reply": "".join(reply_parts),
        "passages": passages,
    }
    if metadata.get("synthesis"):
        result["synthesis"] = metadata["synthesis"]
    return result


def stream_reflect_response(message: str, lang: str = "en") -> Generator[dict, None, None]:
    """
    Stream a reflection response token by token.

    Yields:
        - {"type": "token", "token": "..."} for each token
        - {"type": "done", "done": True} when complete
    """
    llm = get_llm()
    messages = [
        {"role": "system", "content": _get_reflect_prompt(lang)},
        {"role": "user", "content": message},
    ]

    accumulated = ""
    for chunk in llm.stream(messages):
        if chunk.content:
            accumulated += chunk.content
            yield {"type": "token", "token": chunk.content}
            if _detect_repetition(accumulated):
                break

    yield {"type": "done", "done": True}


def query_reflect(message: str, lang: str = "en") -> str:
    """Generate a Proustian reflection response (non-RAG)."""
    llm = get_llm()
    messages = [
        {"role": "system", "content": _get_reflect_prompt(lang)},
        {"role": "user", "content": message},
    ]
    response = llm.invoke(messages)
    return response.content


def check_pinecone_connection() -> dict:
    """Check if Pinecone is properly configured and accessible."""
    try:
        index = get_pinecone_index()
        stats = index.describe_index_stats()
        return {
            "connected": True,
            "details": {
                "index_name": config.PINECONE_INDEX_NAME,
                "total_vectors": stats.total_vector_count,
                "dimension": stats.dimension,
            },
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
        }
