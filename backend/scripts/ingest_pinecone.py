#!/usr/bin/env python3
"""
Ingest Proust passages into Pinecone vector database.

Supports bilingual passages (parsed_clean_bilingual.json) with dual
namespaces: EN text is embedded into namespace "en", FR text into namespace
"fr". Both namespaces store both text and text_fr in metadata for bilingual
display. At query time, the lang parameter selects which namespace to query.

Usage:
    cd backend
    python scripts/ingest_pinecone.py                          # ingest both namespaces
    python scripts/ingest_pinecone.py --lang en                # EN namespace only
    python scripts/ingest_pinecone.py --lang fr                # FR namespace only
    python scripts/ingest_pinecone.py --index proust-index-v2  # custom index name

Prerequisites:
    1. Create a Pinecone account at https://www.pinecone.io/
    2. The script will create the index automatically with:
       - Dimensions: 1536 (Cohere embed-v4.0)
       - Metric: cosine
    3. Copy .env.example to .env and add your PINECONE_API_KEY and COHERE_API_KEY
"""
import argparse
import json
import os
import sys
import time
import warnings
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from text_utils import clean_passage_text
from langchain_cohere import CohereEmbeddings
from pinecone import Pinecone, ServerlessSpec

# Load environment variables
load_dotenv()

# Configuration
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
COHERE_API_KEY = os.getenv("COHERE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "proust-index-v2")
COHERE_EMBED_MODEL = os.getenv("COHERE_EMBED_MODEL", "embed-v4.0")
EMBEDDING_DIMENSION = 1536
BATCH_SIZE = 96  # Cohere API batch limit


def load_parsed_data(filepath: str = None) -> list[dict]:
    """Load passages, preferring bilingual > parsed_clean > parsed."""
    backend_dir = Path(__file__).parent.parent

    if filepath:
        paths_to_try = [Path(filepath)]
    else:
        paths_to_try = [
            backend_dir / "parsed_clean_bilingual.json",
            backend_dir / "parsed_clean.json",
            backend_dir / "parsed.json",
        ]

    for path in paths_to_try:
        if path.exists():
            if path.name == "parsed.json" and not filepath:
                warnings.warn(
                    "parsed_clean.json not found — falling back to parsed.json. "
                    "Run 'python scripts/sanitize_passages.py' first for best results."
                )
            print(f"Loading data from: {path}")
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)

    raise FileNotFoundError(
        f"Could not find passage data in any of: {[str(p) for p in paths_to_try]}"
    )


def create_passages(raw_passages: list[dict]) -> list[dict]:
    """Convert raw passages to cleaned records with text and metadata.

    If passages contain text_fr (bilingual), it is stored in metadata
    for language-switched retrieval.
    """
    passages = []
    skipped = 0
    fr_count = 0

    for passage in raw_passages:
        if passage.get("chapter") is None:
            skipped += 1
            continue

        text = clean_passage_text(passage.get("text", ""))
        if not text or len(text) < 20:
            skipped += 1
            continue

        metadata = {
            "book": passage.get("book", "Unknown"),
            "volume": passage.get("volume", 1),
            "chapter": passage.get("chapter") or "Unknown",
            "index": passage.get("index", 0),
        }

        # Include French text in metadata if available
        text_fr = passage.get("text_fr", "")
        if text_fr:
            metadata["text_fr"] = text_fr
            fr_count += 1

        # Pinecone metadata limit is 40KB per vector.
        # Truncate text fields if combined size is too large.
        MAX_META_BYTES = 38000  # leave headroom for other fields
        total_text = len(text.encode("utf-8")) + len(text_fr.encode("utf-8"))
        if total_text > MAX_META_BYTES:
            half = MAX_META_BYTES // 2
            text = text[:half]
            if text_fr:
                metadata["text_fr"] = text_fr[:half]

        passages.append({
            "id": f"passage-{passage.get('index', len(passages))}",
            "text": text,
            "metadata": metadata,
        })

    if skipped:
        print(f"  Skipped {skipped} passages (empty, too short, or no chapter)")
    if fr_count:
        print(f"  {fr_count} passages have French text")

    return passages


def create_index_if_not_exists(pc: Pinecone, index_name: str) -> None:
    """Create Pinecone index if it doesn't exist."""
    existing_indexes = [idx.name for idx in pc.list_indexes()]

    if index_name not in existing_indexes:
        print(f"Creating index '{index_name}'...")
        pc.create_index(
            name=index_name,
            dimension=EMBEDDING_DIMENSION,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        # Wait for index to be ready
        while not pc.describe_index(index_name).status["ready"]:
            time.sleep(1)
        print(f"Index '{index_name}' created successfully.")
    else:
        print(f"Index '{index_name}' already exists.")


def ingest_to_pinecone(passages: list[dict], namespace: str, text_field: str) -> int:
    """
    Embed passages using text_field and upsert to Pinecone namespace.

    Args:
        passages: List of passage dicts with 'id', 'text', and 'metadata'.
        namespace: Pinecone namespace to upsert into ("en" or "fr").
        text_field: Metadata key to use for embedding ("text" or "text_fr").

    Returns:
        Number of passages ingested.
    """
    print(f"\nInitializing Cohere embedding model: {COHERE_EMBED_MODEL}")
    embeddings = CohereEmbeddings(
        model=COHERE_EMBED_MODEL,
        cohere_api_key=COHERE_API_KEY,
    )

    print("Connecting to Pinecone...")
    pc = Pinecone(api_key=PINECONE_API_KEY)
    create_index_if_not_exists(pc, PINECONE_INDEX_NAME)
    index = pc.Index(PINECONE_INDEX_NAME)

    # Delete existing vectors in this namespace for a clean slate
    print(f"  Clearing namespace '{namespace}'...")
    try:
        index.delete(delete_all=True, namespace=namespace)
    except Exception:
        print(f"  Namespace '{namespace}' not found, skipping clear.")

    print(f"\nIngesting {len(passages)} passages into namespace '{namespace}' "
          f"(embedding on '{text_field}') in batches of {BATCH_SIZE}...")

    total_ingested = 0
    for i in range(0, len(passages), BATCH_SIZE):
        batch = passages[i : i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        total_batches = (len(passages) + BATCH_SIZE - 1) // BATCH_SIZE

        print(f"  Batch {batch_num}/{total_batches} ({len(batch)} passages)...")

        # Embed using the specified text field
        texts = [p["metadata"].get(text_field, p["text"]) if text_field != "text"
                 else p["text"] for p in batch]
        vectors = embeddings.embed_documents(texts)

        # Build upsert records — store text in metadata for retrieval
        records = []
        for p, vec in zip(batch, vectors):
            meta = {**p["metadata"], "text": p["text"]}
            records.append({"id": p["id"], "values": vec, "metadata": meta})

        index.upsert(vectors=records, namespace=namespace)
        total_ingested += len(batch)
        print(f"    Ingested {total_ingested}/{len(passages)}")

    return total_ingested


def verify_ingestion() -> dict:
    """Verify the ingestion by checking index stats per namespace."""
    pc = Pinecone(api_key=PINECONE_API_KEY)
    index = pc.Index(PINECONE_INDEX_NAME)
    stats = index.describe_index_stats()

    result = {
        "total_vectors": stats.total_vector_count,
        "dimension": stats.dimension,
        "namespaces": {},
    }
    for ns, ns_stats in (stats.namespaces or {}).items():
        result["namespaces"][ns] = {"vector_count": ns_stats.vector_count}

    return result


def main():
    """Main ingestion script."""
    global PINECONE_INDEX_NAME

    parser = argparse.ArgumentParser(description="Ingest Proust passages into Pinecone")
    parser.add_argument("--index", default=PINECONE_INDEX_NAME,
                        help=f"Pinecone index name (default: {PINECONE_INDEX_NAME})")
    parser.add_argument("--file", default=None,
                        help="Path to passage data file (auto-detected if not specified)")
    parser.add_argument("--lang", default="both", choices=["en", "fr", "both"],
                        help="Which namespace(s) to populate (default: both)")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Skip confirmation prompt")
    args = parser.parse_args()
    PINECONE_INDEX_NAME = args.index

    print("=" * 60)
    print("ProustGPT Pinecone Ingestion Script")
    print("=" * 60)

    if not PINECONE_API_KEY:
        print("\nERROR: PINECONE_API_KEY not set.")
        sys.exit(1)

    if not COHERE_API_KEY:
        print("\nERROR: COHERE_API_KEY not set.")
        sys.exit(1)

    print("\nStep 1: Loading passage data...")
    raw = load_parsed_data(args.file)
    print(f"  Loaded {len(raw)} raw passages")

    print("\nStep 2: Cleaning passages...")
    passages = create_passages(raw)
    print(f"  Created {len(passages)} clean passages")

    namespaces = []
    if args.lang in ("en", "both"):
        namespaces.append(("en", "text"))
    if args.lang in ("fr", "both"):
        namespaces.append(("fr", "text_fr"))

    print(f"\nReady to ingest to '{PINECONE_INDEX_NAME}'")
    print(f"  Namespaces: {[ns for ns, _ in namespaces]}")
    print(f"  Embedding: {COHERE_EMBED_MODEL} ({EMBEDDING_DIMENSION} dims)")
    if not args.yes:
        response = input("Continue? [y/N]: ").strip().lower()
        if response != "y":
            print("Aborted.")
            sys.exit(0)

    step = 3
    for namespace, text_field in namespaces:
        if namespace == "fr":
            # Filter to passages that have French text
            ns_passages = [p for p in passages if p["metadata"].get("text_fr")]
            print(f"\nStep {step}: Embedding & upserting namespace '{namespace}' "
                  f"({len(ns_passages)} passages with FR text)...")
        else:
            ns_passages = passages
            print(f"\nStep {step}: Embedding & upserting namespace '{namespace}' "
                  f"({len(ns_passages)} passages)...")

        total = ingest_to_pinecone(ns_passages, namespace=namespace, text_field=text_field)
        print(f"  Ingested {total} passages into namespace '{namespace}'")
        step += 1

    print(f"\nStep {step}: Verifying...")
    stats = verify_ingestion()
    print(f"  Index stats: {stats}")

    print("\n" + "=" * 60)
    print("SUCCESS: Ingestion complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
