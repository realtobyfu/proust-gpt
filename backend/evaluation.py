"""
RAG evaluation metrics for ProustGPT.

Measures retrieval quality, answer faithfulness, and answer relevance
using a curated Proust-specific evaluation dataset.
"""
import time
from dataclasses import dataclass, field
from typing import Optional

from retrieval import retrieve_passages, get_llm, stream_rag_response


@dataclass
class RAGMetrics:
    """Metrics for a single evaluation query."""
    question: str
    retrieval_precision: float  # % of retrieved docs that hit expected topics
    retrieval_recall: float     # % of expected topics covered by retrieved docs
    answer_relevance: float     # 0-1: is the answer relevant to the question?
    faithfulness: float         # 0-1: is the answer grounded in context?
    latency_ms: float           # End-to-end latency in milliseconds
    answer: str = ""
    retrieved_texts: list[str] = field(default_factory=list)


@dataclass
class EvalSummary:
    """Aggregate metrics across the evaluation dataset."""
    num_queries: int
    avg_retrieval_precision: float
    avg_retrieval_recall: float
    avg_answer_relevance: float
    avg_faithfulness: float
    avg_latency_ms: float
    per_query: list[RAGMetrics]


# ── Evaluation dataset ───────────────────────────────────────────────────────

EVAL_DATASET = [
    {
        "question": "What triggers the narrator's involuntary memory in Swann's Way?",
        "expected_topics": ["madeleine", "tea", "lime-blossom", "combray", "memory"],
    },
    {
        "question": "Describe Swann's relationship with Odette",
        "expected_topics": ["jealousy", "love", "verdurin", "cattleya", "swann", "odette"],
    },
    {
        "question": "What is the significance of the two 'ways' at Combray?",
        "expected_topics": ["swann", "guermantes", "combray", "walk", "way", "path"],
    },
    {
        "question": "How does the narrator describe falling asleep?",
        "expected_topics": ["sleep", "bed", "room", "night", "dream", "waking"],
    },
    {
        "question": "What role does the magic lantern play in the narrator's childhood?",
        "expected_topics": ["lantern", "golo", "geneviève", "brabant", "bedroom", "light"],
    },
    {
        "question": "Describe the hawthorn flowers scene in Combray",
        "expected_topics": ["hawthorn", "flower", "hedge", "pink", "white", "church"],
    },
    {
        "question": "What is the narrator's relationship with his grandmother?",
        "expected_topics": ["grandmother", "love", "health", "walk", "balbec"],
    },
    {
        "question": "How does Proust portray Baron de Charlus?",
        "expected_topics": ["charlus", "aristocrat", "morel", "inversion", "pride"],
    },
    {
        "question": "What is the goodnight kiss scene about?",
        "expected_topics": ["kiss", "mother", "night", "bed", "anguish", "anxiety"],
    },
    {
        "question": "How does the narrator experience the Guermantes salon?",
        "expected_topics": ["guermantes", "duchess", "salon", "aristocracy", "society"],
    },
    {
        "question": "What does Proust say about the nature of habit?",
        "expected_topics": ["habit", "change", "comfort", "adaptation", "familiar"],
    },
    {
        "question": "Describe the narrator's experience with Albertine",
        "expected_topics": ["albertine", "love", "jealousy", "captive", "prisoner"],
    },
    {
        "question": "What is the significance of the steeples of Martinville?",
        "expected_topics": ["steeple", "martinville", "writing", "impression", "carriage"],
    },
    {
        "question": "How does time function as a theme in the novel?",
        "expected_topics": ["time", "memory", "past", "change", "lost"],
    },
    {
        "question": "What is the role of art and literature in the narrator's life?",
        "expected_topics": ["art", "writing", "bergotte", "elstir", "vinteuil", "book"],
    },
]


# ── Metric functions ─────────────────────────────────────────────────────────

def evaluate_retrieval(retrieved_texts: list[str], expected_topics: list[str]) -> dict:
    """
    Evaluate retrieval quality by checking how many expected topics
    appear in the retrieved passages.

    Returns:
        dict with 'precision' and 'recall' (both 0-1).
    """
    if not retrieved_texts:
        return {"precision": 0.0, "recall": 0.0}

    # Count how many retrieved docs contain at least one expected topic
    hits = 0
    for text in retrieved_texts:
        text_lower = text.lower()
        if any(topic.lower() in text_lower for topic in expected_topics):
            hits += 1

    # Count how many expected topics appear in at least one retrieved doc
    combined_text = " ".join(retrieved_texts).lower()
    topics_found = sum(
        1 for topic in expected_topics if topic.lower() in combined_text
    )

    precision = hits / len(retrieved_texts) if retrieved_texts else 0.0
    recall = topics_found / len(expected_topics) if expected_topics else 0.0

    return {"precision": precision, "recall": recall}


def evaluate_faithfulness(answer: str, context: str, llm=None) -> float:
    """
    Check if the answer is grounded in the retrieved context using LLM-as-judge.

    Returns:
        Float 0-1 score for faithfulness.
    """
    if not answer or not context:
        return 0.0

    if llm is None:
        llm = get_llm()

    prompt = (
        "You are an evaluation judge. Given the context and answer below, "
        "rate from 0.0 to 1.0 how well the answer is supported by the context. "
        "A score of 1.0 means every claim in the answer is directly supported by the context. "
        "A score of 0.0 means the answer is entirely fabricated.\n\n"
        "Respond with ONLY a number between 0.0 and 1.0, nothing else.\n\n"
        f"Context:\n{context[:3000]}\n\n"
        f"Answer:\n{answer[:1500]}\n\n"
        "Score:"
    )

    try:
        response = llm.invoke(prompt)
        score_text = response.content.strip()
        # Extract first float-like value from response
        for part in score_text.split():
            try:
                score = float(part)
                return max(0.0, min(1.0, score))
            except ValueError:
                continue
        return 0.5
    except Exception:
        return 0.5


def evaluate_answer_relevance(question: str, answer: str, llm=None) -> float:
    """
    Check if the answer is relevant to the question using LLM-as-judge.

    Returns:
        Float 0-1 score for answer relevance.
    """
    if not answer:
        return 0.0

    if llm is None:
        llm = get_llm()

    prompt = (
        "You are an evaluation judge. Given the question and answer below, "
        "rate from 0.0 to 1.0 how relevant and helpful the answer is to the question. "
        "A score of 1.0 means the answer directly and thoroughly addresses the question. "
        "A score of 0.0 means the answer is completely irrelevant.\n\n"
        "Respond with ONLY a number between 0.0 and 1.0, nothing else.\n\n"
        f"Question: {question}\n\n"
        f"Answer:\n{answer[:1500]}\n\n"
        "Score:"
    )

    try:
        response = llm.invoke(prompt)
        score_text = response.content.strip()
        for part in score_text.split():
            try:
                score = float(part)
                return max(0.0, min(1.0, score))
            except ValueError:
                continue
        return 0.5
    except Exception:
        return 0.5


# ── Full evaluation runner ───────────────────────────────────────────────────

def run_evaluation(
    dataset: Optional[list[dict]] = None,
    use_llm_judge: bool = True,
    verbose: bool = False,
) -> EvalSummary:
    """
    Run the full RAG evaluation pipeline over the dataset.

    Args:
        dataset: List of eval items (defaults to EVAL_DATASET).
        use_llm_judge: Whether to use LLM for faithfulness/relevance scoring.
        verbose: Print per-query results during evaluation.

    Returns:
        EvalSummary with aggregate and per-query metrics.
    """
    if dataset is None:
        dataset = EVAL_DATASET

    llm = get_llm() if use_llm_judge else None
    results: list[RAGMetrics] = []

    for i, item in enumerate(dataset):
        question = item["question"]
        expected_topics = item["expected_topics"]

        if verbose:
            print(f"\n[{i + 1}/{len(dataset)}] {question}")

        # Time the full RAG pipeline
        start = time.time()

        # Run RAG and collect answer + passages
        answer_parts = []
        passages = []
        for event in stream_rag_response(question):
            if event["type"] == "token":
                answer_parts.append(event["token"])
            elif event["type"] == "sources":
                passages = event.get("passages", [])

        latency_ms = (time.time() - start) * 1000
        answer = "".join(answer_parts)
        retrieved_texts = [p.get("text", "") for p in passages]

        # Retrieval metrics
        ret_metrics = evaluate_retrieval(retrieved_texts, expected_topics)

        # LLM-as-judge metrics
        if use_llm_judge and answer:
            context = "\n\n".join(retrieved_texts)
            faithfulness = evaluate_faithfulness(answer, context, llm)
            relevance = evaluate_answer_relevance(question, answer, llm)
        else:
            faithfulness = 0.0
            relevance = 0.0

        metrics = RAGMetrics(
            question=question,
            retrieval_precision=ret_metrics["precision"],
            retrieval_recall=ret_metrics["recall"],
            answer_relevance=relevance,
            faithfulness=faithfulness,
            latency_ms=latency_ms,
            answer=answer,
            retrieved_texts=retrieved_texts,
        )
        results.append(metrics)

        if verbose:
            print(f"  Precision: {metrics.retrieval_precision:.2f}")
            print(f"  Recall:    {metrics.retrieval_recall:.2f}")
            if use_llm_judge:
                print(f"  Relevance: {metrics.answer_relevance:.2f}")
                print(f"  Faithful:  {metrics.faithfulness:.2f}")
            print(f"  Latency:   {metrics.latency_ms:.0f}ms")

    # Aggregate
    n = len(results)
    summary = EvalSummary(
        num_queries=n,
        avg_retrieval_precision=sum(r.retrieval_precision for r in results) / n if n else 0,
        avg_retrieval_recall=sum(r.retrieval_recall for r in results) / n if n else 0,
        avg_answer_relevance=sum(r.answer_relevance for r in results) / n if n else 0,
        avg_faithfulness=sum(r.faithfulness for r in results) / n if n else 0,
        avg_latency_ms=sum(r.latency_ms for r in results) / n if n else 0,
        per_query=results,
    )

    return summary
