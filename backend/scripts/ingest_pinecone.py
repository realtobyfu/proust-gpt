#!/usr/bin/env python3
"""
Ingest Proust passages from parsed.json into Pinecone vector database.

Usage:
    cd backend
    python scripts/ingest_pinecone.py

Prerequisites:
    1. Create a Pinecone account at https://www.pinecone.io/
    2. The script will create the index automatically with:
       - Dimensions: 1536 (Cohere embed-v4.0)
       - Metric: cosine
    3. Copy .env.example to .env and add your PINECONE_API_KEY and COHERE_API_KEY
"""
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
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "proust-index")
COHERE_EMBED_MODEL = os.getenv("COHERE_EMBED_MODEL", "embed-v4.0")
EMBEDDING_DIMENSION = 1536
BATCH_SIZE = 96  # Cohere API batch limit


def load_parsed_data(filepath: str = None) -> list[dict]:
    """Load passages, preferring parsed_clean.json over parsed.json."""
    backend_dir = Path(__file__).parent.parent

    if filepath:
        paths_to_try = [Path(filepath)]
    else:
        paths_to_try = [
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
    """Convert raw passages to cleaned records with text and metadata."""
    passages = []
    skipped = 0

    for passage in raw_passages:
        if passage.get("chapter") is None:
            skipped += 1
            continue

        text = clean_passage_text(passage.get("text", ""))
        if not text or len(text) < 20:
            skipped += 1
            continue

        passages.append({
            "id": f"passage-{passage.get('index', len(passages))}",
            "text": text,
            "metadata": {
                "book": passage.get("book", "Unknown"),
                "volume": passage.get("volume", 1),
                "chapter": passage.get("chapter") or "Unknown",
                "index": passage.get("index", 0),
            },
        })

    if skipped:
        print(f"  Skipped {skipped} passages (empty, too short, or no chapter)")

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


def ingest_to_pinecone(passages: list[dict]) -> int:
    """
    Embed passages with Cohere and upsert to Pinecone.

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

    print(f"\nIngesting {len(passages)} passages in batches of {BATCH_SIZE}...")

    total_ingested = 0
    for i in range(0, len(passages), BATCH_SIZE):
        batch = passages[i : i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        total_batches = (len(passages) + BATCH_SIZE - 1) // BATCH_SIZE

        print(f"  Batch {batch_num}/{total_batches} ({len(batch)} passages)...")

        # Embed the batch
        texts = [p["text"] for p in batch]
        vectors = embeddings.embed_documents(texts)

        # Build upsert records — store text in metadata for retrieval
        records = []
        for p, vec in zip(batch, vectors):
            meta = {**p["metadata"], "text": p["text"]}
            records.append({"id": p["id"], "values": vec, "metadata": meta})

        index.upsert(vectors=records)
        total_ingested += len(batch)
        print(f"    Ingested {total_ingested}/{len(passages)}")

    return total_ingested


def verify_ingestion() -> dict:
    """Verify the ingestion by checking index stats."""
    pc = Pinecone(api_key=PINECONE_API_KEY)
    index = pc.Index(PINECONE_INDEX_NAME)
    stats = index.describe_index_stats()

    return {
        "total_vectors": stats.total_vector_count,
        "dimension": stats.dimension,
    }


def main():
    """Main ingestion script."""
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
    raw = load_parsed_data()
    print(f"  Loaded {len(raw)} raw passages")

    print("\nStep 2: Cleaning passages...")
    passages = create_passages(raw)
    print(f"  Created {len(passages)} clean passages")

    print(f"\nReady to ingest {len(passages)} passages to '{PINECONE_INDEX_NAME}'")
    print(f"  Embedding: {COHERE_EMBED_MODEL} ({EMBEDDING_DIMENSION} dims)")
    response = input("Continue? [y/N]: ").strip().lower()
    if response != "y":
        print("Aborted.")
        sys.exit(0)

    print("\nStep 3: Embedding & upserting...")
    total = ingest_to_pinecone(passages)

    print("\nStep 4: Verifying...")
    stats = verify_ingestion()
    print(f"  Index stats: {stats}")

    print("\n" + "=" * 60)
    print(f"SUCCESS: Ingested {total} passages!")
    print("=" * 60)


if __name__ == "__main__":
    main()
