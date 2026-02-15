#!/usr/bin/env python3
"""
RAG Evaluation CLI for ProustGPT.

Runs the evaluation suite against the live RAG pipeline and prints
a results table. Optionally exports results to JSON.

Usage:
    python scripts/evaluate.py                  # Full eval with LLM judge
    python scripts/evaluate.py --fast           # Retrieval metrics only (no LLM judge)
    python scripts/evaluate.py --export results.json  # Export results
    python scripts/evaluate.py -n 5             # Only run first 5 questions
"""
import argparse
import json
import sys
import os

# Ensure the backend directory is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluation import run_evaluation, EVAL_DATASET


def print_table(summary):
    """Print a formatted results table."""
    print("\n" + "=" * 72)
    print("  ProustGPT RAG Evaluation Results")
    print("=" * 72)

    # Per-query results
    header = f"{'#':<3} {'Question':<45} {'Prec':>5} {'Rec':>5} {'Rel':>5} {'Faith':>5} {'ms':>7}"
    print(f"\n{header}")
    print("-" * 72)

    for i, m in enumerate(summary.per_query):
        q = m.question[:43] + ".." if len(m.question) > 45 else m.question
        print(
            f"{i + 1:<3} {q:<45} "
            f"{m.retrieval_precision:>5.2f} "
            f"{m.retrieval_recall:>5.2f} "
            f"{m.answer_relevance:>5.2f} "
            f"{m.faithfulness:>5.2f} "
            f"{m.latency_ms:>6.0f}"
        )

    # Aggregate
    print("-" * 72)
    print(
        f"{'':>3} {'AVERAGE':<45} "
        f"{summary.avg_retrieval_precision:>5.2f} "
        f"{summary.avg_retrieval_recall:>5.2f} "
        f"{summary.avg_answer_relevance:>5.2f} "
        f"{summary.avg_faithfulness:>5.2f} "
        f"{summary.avg_latency_ms:>6.0f}"
    )
    print("=" * 72)

    print(f"\nQueries evaluated: {summary.num_queries}")
    print(f"Avg Retrieval Precision@5: {summary.avg_retrieval_precision:.3f}")
    print(f"Avg Retrieval Recall:      {summary.avg_retrieval_recall:.3f}")
    print(f"Avg Answer Relevance:      {summary.avg_answer_relevance:.3f}")
    print(f"Avg Faithfulness:          {summary.avg_faithfulness:.3f}")
    print(f"Avg Latency:               {summary.avg_latency_ms:.0f}ms")


def export_json(summary, path):
    """Export evaluation results to JSON."""
    data = {
        "num_queries": summary.num_queries,
        "avg_retrieval_precision": summary.avg_retrieval_precision,
        "avg_retrieval_recall": summary.avg_retrieval_recall,
        "avg_answer_relevance": summary.avg_answer_relevance,
        "avg_faithfulness": summary.avg_faithfulness,
        "avg_latency_ms": summary.avg_latency_ms,
        "per_query": [
            {
                "question": m.question,
                "retrieval_precision": m.retrieval_precision,
                "retrieval_recall": m.retrieval_recall,
                "answer_relevance": m.answer_relevance,
                "faithfulness": m.faithfulness,
                "latency_ms": m.latency_ms,
                "answer_preview": m.answer[:200],
                "num_passages": len(m.retrieved_texts),
            }
            for m in summary.per_query
        ],
    }

    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\nResults exported to {path}")


def main():
    parser = argparse.ArgumentParser(description="ProustGPT RAG Evaluation")
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Skip LLM-as-judge metrics (retrieval metrics only)",
    )
    parser.add_argument(
        "--export",
        type=str,
        metavar="FILE",
        help="Export results to JSON file",
    )
    parser.add_argument(
        "-n",
        type=int,
        default=None,
        help="Number of eval questions to run (default: all)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print per-query details during evaluation",
    )
    args = parser.parse_args()

    dataset = EVAL_DATASET
    if args.n is not None:
        dataset = dataset[: args.n]

    print(f"Running evaluation on {len(dataset)} queries...")
    if args.fast:
        print("(Fast mode: skipping LLM-as-judge metrics)")

    summary = run_evaluation(
        dataset=dataset,
        use_llm_judge=not args.fast,
        verbose=args.verbose,
    )

    print_table(summary)

    if args.export:
        export_json(summary, args.export)


if __name__ == "__main__":
    main()
