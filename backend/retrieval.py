"""
LangChain orchestration for ProustGPT.
Provides embeddings (Cohere), LLM (Groq), reranking (Cohere),
vector store (Pinecone SDK), and RAG retrieval + streaming.
"""
import re
from typing import Generator, Optional

from langchain_cohere import CohereEmbeddings, CohereRerank
from langchain_groq import ChatGroq
from langchain_core.documents import Document
from pinecone import Pinecone

from config import config
from text_utils import clean_passage_text


# ── Module-level singletons (lazy loaded) ────────────────────────────────────

_embeddings: Optional[CohereEmbeddings] = None
_llm: Optional[ChatGroq] = None
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

REFLECT_SYSTEM_PROMPT = """You are a wise, reflective conversationalist in the spirit of Marcel Proust. You help the reader contemplate their inner life, drawing on themes of memory, time, sensation, and the self.
Write in flowing prose paragraphs — no lists, no headings. Use *italics* sparingly. Match length to the question's depth. End with one thoughtful question to invite deeper reflection."""

REFLECT_SYSTEM_PROMPT_FR = """Vous êtes un conversateur sage et réfléchi dans l'esprit de Marcel Proust. Vous aidez le lecteur à contempler sa vie intérieure, en vous appuyant sur les thèmes de la mémoire, du temps, de la sensation et du moi.
Écrivez en paragraphes de prose fluide — pas de listes, pas de titres. Utilisez les *italiques* avec parcimonie. Adaptez la longueur à la profondeur de la question. Terminez par une question réfléchie pour inviter à une réflexion plus profonde. Répondez en français."""

_RAG_FALLBACK_TEMPLATE = """You are a literary companion for Marcel Proust's "In Search of Lost Time."
Write in flowing prose — no lists, no headings. Be concise: aim for 2-3 short paragraphs. Quote brief phrases from the passages directly rather than summarizing at length. Do not restate the question. End with one thoughtful follow-up question to deepen the reader's exploration.

When your answer draws on a specific passage, include [1], [2], etc. at the end of the relevant sentence. If no specific passage is needed, answer without bracketed references.

Context passages:
{context}

Reader's question: {question}"""

_RAG_FALLBACK_TEMPLATE_FR = """Vous êtes un compagnon littéraire pour « À la recherche du temps perdu » de Marcel Proust.
Écrivez en prose fluide — pas de listes, pas de titres. Soyez concis : visez 2-3 courts paragraphes. Citez de brèves phrases des passages directement. Ne reformulez pas la question. Terminez par une question de suivi réfléchie pour approfondir l'exploration du lecteur. Répondez en français.

Lorsque votre réponse s'appuie sur un passage spécifique, incluez [1], [2], etc. à la fin de la phrase concernée. Si aucun passage spécifique n'est nécessaire, répondez sans références entre crochets.

Passages de contexte :
{context}

Question du lecteur : {question}"""


def _get_reflect_prompt(lang: str = "en") -> str:
    return REFLECT_SYSTEM_PROMPT_FR if lang == "fr" else REFLECT_SYSTEM_PROMPT


def _get_rag_fallback_template(lang: str = "en") -> str:
    return _RAG_FALLBACK_TEMPLATE_FR if lang == "fr" else _RAG_FALLBACK_TEMPLATE


# ── Retrieval helpers ─────────────────────────────────────────────────────────

def _pinecone_query(
    query: str,
    top_k: int,
    lang: str = "en",
    metadata_filter: dict | None = None,
) -> list[Document]:
    embeddings = get_embeddings()
    query_vector = embeddings.embed_query(query)

    index = get_pinecone_index()
    query_kwargs: dict = dict(
        vector=query_vector,
        top_k=top_k,
        include_metadata=True,
        namespace=lang,
    )
    if metadata_filter:
        query_kwargs["filter"] = metadata_filter
    results = index.query(**query_kwargs)

    docs = []
    for match in results.matches:
        metadata = match.metadata or {}
        text_en = metadata.pop("text", "")
        text_fr = metadata.pop("text_fr", "")
        # Use French text when requested; fall back to English if FR is empty
        if lang == "fr" and text_fr:
            page_content = text_fr
        else:
            page_content = text_en
        # Store both texts in metadata for downstream use
        metadata["_text_en"] = text_en
        metadata["_text_fr"] = text_fr
        docs.append(Document(page_content=page_content, metadata=metadata))
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


def _fetch_adjacent_passages(indices: set[int], lang: str = "en") -> dict[int, str]:
    if not indices:
        return {}
    ids = [f"passage-{i}" for i in indices]
    index = get_pinecone_index()
    result = index.fetch(ids=ids, namespace=lang)
    texts = {}
    for vec_id, vec_data in result.vectors.items():
        idx = int(vec_id.replace("passage-", ""))
        if lang == "fr":
            text = vec_data.metadata.get("text_fr", "") or vec_data.metadata.get("text", "")
        else:
            text = vec_data.metadata.get("text", "")
        texts[idx] = text
    return texts


def _stitch_context(docs: list[Document], lang: str = "en") -> list[Document]:
    needed: set[int] = set()
    for doc in docs:
        idx = doc.metadata.get("index")
        if idx is None:
            continue
        if _starts_mid_sentence(doc.page_content) and idx > 1:
            needed.add(idx - 1)
        if _ends_mid_sentence(doc.page_content):
            needed.add(idx + 1)

    adjacent = _fetch_adjacent_passages(needed, lang=lang)

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

def _format_passages(docs: list[Document], relevance_summaries: list[str] | None = None, lang: str = "en") -> list[dict]:
    passages = []
    for i, doc in enumerate(docs):
        text_en = doc.metadata.get("_text_en", "") or doc.page_content
        text_fr = doc.metadata.get("_text_fr", "")
        p = {
            "book": doc.metadata.get("book", "Unknown"),
            "chapter": doc.metadata.get("chapter", "Unknown"),
            "text": clean_passage_text(text_en),
            "text_fr": clean_passage_text(text_fr) if text_fr else "",
            "volume": doc.metadata.get("volume"),
            "index": doc.metadata.get("index"),
            "citation_index": i + 1,
        }
        if relevance_summaries and i < len(relevance_summaries):
            p["relevance_summary"] = relevance_summaries[i]
        passages.append(p)
    return passages


def retrieve_passages(query: str, lang: str = "en") -> list[Document]:
    candidates = _pinecone_query(query, top_k=config.RETRIEVAL_CANDIDATES, lang=lang)
    reranker = get_reranker()
    reranked = list(reranker.compress_documents(candidates, query))
    return _stitch_context(reranked, lang=lang)


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


# ── Public API ────────────────────────────────────────────────────────────────

def stream_rag_response(query: str, lang: str = "en") -> Generator[dict, None, None]:
    """
    Stream a RAG response: retrieve passages, then stream one LLM call.

    Yields:
        - {"type": "token", "token": "..."} for each token/chunk
        - {"type": "sources", "passages": [...]} for retrieved passages
        - {"type": "done", "done": True} when complete
    """
    docs = retrieve_passages(query, lang=lang)
    context = "\n\n---\n\n".join(
        f"[{i+1}] {doc.page_content}"
        for i, doc in enumerate(docs)
    )
    prompt = _get_rag_fallback_template(lang).format(context=context, question=query)

    llm = get_llm()
    accumulated = ""
    for chunk in llm.stream(prompt):
        if chunk.content:
            accumulated += chunk.content
            yield {"type": "token", "token": chunk.content}
            if _detect_repetition(accumulated):
                break

    yield {"type": "sources", "passages": _format_passages(docs, lang=lang)}
    yield {"type": "done", "done": True}


def query_rag(query: str, lang: str = "en") -> dict:
    """
    Execute a RAG query (non-streaming).

    Returns:
        Dictionary with 'reply' and 'passages' keys.
    """
    reply_parts = []
    passages = []

    for event in stream_rag_response(query, lang=lang):
        if event["type"] == "token":
            reply_parts.append(event["token"])
        elif event["type"] == "sources":
            passages = event["passages"]

    return {
        "reply": "".join(reply_parts),
        "passages": passages,
    }


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
                "namespaces": {
                    ns: {"vector_count": ns_stats.vector_count}
                    for ns, ns_stats in (stats.namespaces or {}).items()
                },
            },
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
        }
