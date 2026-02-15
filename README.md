Initial Screen:
![screenshot](screenshot-1.png)


# ProustGPT

A full-stack web application combining RAG (Retrieval-Augmented Generation) with introspective AI conversation for exploring Marcel Proust's *In Search of Lost Time* (*A la recherche du temps perdu*) — in both English and French.

**Two modes:**
1. **Explore Lost Time** — RAG-based passage retrieval from Proust's text (bilingual)
2. **Reflect on My Day** — Introspective conversation in Proust's style

## Technology Stack

### Frontend
- **React** + **TypeScript** (Vite)
- **Styled Components** with transient props
- **React Router**
- Server-Sent Events (SSE) for streaming responses

### Backend
- **FastAPI** with streaming SSE endpoints
- **Groq API** with Kimi K2 (`moonshotai/kimi-k2-instruct`, 131K context)
- **Cohere** embed-v4.0 (1536-dim multilingual embeddings) + rerank-v3.5
- **Pinecone** serverless vector database
- **spaCy** for entity extraction

## Setup

### Prerequisites
- **Node.js** (version 18+)
- **Python 3.11+**
- API keys for Pinecone, Groq, and Cohere

### Frontend

```bash
npm install
npm run dev          # Start dev server at localhost:5173
npm run build        # Production build
```

### Backend

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
cp .env.example .env
# Edit .env with your PINECONE_API_KEY, GROQ_API_KEY, COHERE_API_KEY
python server.py     # Start server at localhost:5000
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PINECONE_API_KEY` | Yes | — | Pinecone vector database |
| `GROQ_API_KEY` | Yes | — | Groq LLM API |
| `COHERE_API_KEY` | Yes | — | Cohere embeddings and reranking |
| `PINECONE_INDEX_NAME` | No | `proust-index` | Pinecone index name |
| `LLM_MODEL_NAME` | No | `moonshotai/kimi-k2-instruct` | LLM model |

## Bilingual Alignment Pipeline

The app serves Proust's text in both English and French. Aligning two translations paragraph-by-paragraph is non-trivial because the English and French texts have different paragraph structures — the English comes from Standard Ebooks (Moncrieff translation, vols 1-6) and Project Gutenberg Australia (Hudson translation, vol 7), while the French comes from Wikisource (original Proust text). Translators often split, merge, or restructure paragraphs differently.

### The Problem

A naive approach — aligning paragraphs by their position (paragraph 5 in EN = paragraph 5 in FR) — breaks down when paragraph counts differ. For example, Volume 3 Chapter 1 has 872 EN paragraphs but only 417 FR paragraphs. Proportional position mapping produces systematic drift: by the end of a long chapter, the French text can be pages off from the English. This means users reading the corpus would see French text that doesn't correspond to the English passage beside it.

### The Solution: Semantic Embedding Alignment

We use **Cohere embed-v4.0** (a multilingual embedding model) to semantically match paragraphs across languages:

1. **Split** each chapter into paragraphs (double-newline boundaries) — paragraph boundaries are preserved
2. **Embed** all EN and FR paragraphs with Cohere embed-v4.0 — the model maps semantically equivalent text in different languages to nearby points in embedding space
3. **Compute** a cosine similarity matrix between all EN and FR paragraphs within each chapter
4. **Align** using dynamic programming with a monotonicity constraint — EN paragraph *i* must map to a FR paragraph index >= EN paragraph *i-1*'s mapping, preserving reading order while maximizing total semantic similarity
5. **Co-chunk** the aligned pairs: merge short passages (<100 chars), split long passages (>1500 chars) at sentence boundaries, keeping EN and FR text together

This produces ~12,900 bilingual passage pairs with 99.98% French coverage and an average cross-language cosine similarity of 0.75.

### Pipeline Scripts

Run from the `backend/` directory:

```bash
# 1. Download English corpus (Standard Ebooks vols 1-6, PG Australia vol 7)
python scripts/download_english_corpus.py

# 2. Download French corpus (Wikisource)
python scripts/download_french_corpus.py

# 3. Semantic alignment (requires COHERE_API_KEY in .env)
python scripts/align_semantic.py              # ~2 min with production key
python scripts/align_semantic.py --delay 12   # ~20 min with trial key

# 4. Co-chunk into final passages
python scripts/chunk_bilingual.py

# 5. Verify alignment quality
python scripts/verify_alignment.py

# 6. Ingest into Pinecone
python scripts/ingest_pinecone.py --index proust-index-v2
```

A non-semantic fallback script (`align_paragraphs.py`) uses proportional position mapping if you don't have a Cohere API key, but produces lower-quality alignment.

## RAG Pipeline

1. **Query** — User asks a question (English or French)
2. **Embed** — Cohere embed-v4.0 (multilingual, 1536-dim)
3. **Retrieve** — Pinecone vector search (k=20 candidates)
4. **Rerank** — Cohere rerank-v3.5 (top 5)
5. **Generate** — Groq API with Kimi K2 (131K context, streaming)

French queries work naturally because Cohere embed-v4.0 is multilingual — a French question finds English-embedded passages that are semantically equivalent. The corresponding French text is stored in Pinecone metadata and returned when `lang=fr`.

## API Endpoints

**Streaming (SSE):**
- `POST /api/explore_lost_time/stream` — Streaming RAG with token-by-token response
- `POST /api/reflect/stream` — Streaming reflection conversation

**Non-Streaming:**
- `POST /api/explore_lost_time` — RAG retrieval, returns `{passages, reply}`
- `POST /api/reflect` — Introspective response, returns `{reply}`

**Health:**
- `GET /health` — Health check with Pinecone/LLM status

## Project Structure

```
src/                    # React frontend (Vite + TypeScript)
├── App.tsx             # Routes: / -> LandingPage, /chat -> ChatPage
├── ChatPage.tsx        # Main chat interface with streaming
├── components/
│   └── PassageDisplay.tsx
└── hooks/
    └── useStreamingQuery.ts

backend/                # FastAPI + Python
├── server.py           # API endpoints (streaming + non-streaming)
├── retrieval.py        # RAG pipeline (Groq, Cohere, Pinecone)
├── config.py           # Configuration (Pydantic BaseSettings)
├── corpus.py           # Local corpus loading (bilingual)
├── text_utils.py       # Text cleaning (OCR artifact fixes)
├── scripts/
│   ├── download_english_corpus.py   # EN from Standard Ebooks + PG Australia
│   ├── download_french_corpus.py    # FR from Wikisource
│   ├── align_semantic.py            # Semantic alignment (Cohere embeddings + DP)
│   ├── align_paragraphs.py          # Fallback proportional alignment
│   ├── chunk_bilingual.py           # Bilingual co-chunking
│   ├── verify_alignment.py          # Alignment quality checks
│   ├── ingest_pinecone.py           # Pinecone ingestion
│   └── evaluate.py                  # RAG evaluation suite
└── parsed_clean_bilingual.json      # Final bilingual passages (~12,900)
```

## Work in Progress

- [ ] Complete the Combray gallery page
- [ ] Conversation history persistence

## License

This project is licensed under the [Apache 2.0 License](LICENSE).

## Acknowledgments

- **Marcel Proust** — for writing the greatest novel of the 20th century
- **C.K. Scott Moncrieff** — English translation (Standard Ebooks edition)
- **Wikisource** — French public domain text
- **Cohere** — multilingual embeddings for cross-language alignment
- **Groq** — fast LLM inference
