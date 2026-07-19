# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ProustGPT is a full-stack web application combining RAG (Retrieval-Augmented Generation) with introspective AI conversation for exploring Marcel Proust's *In Search of Lost Time*.

**Two modes:**
1. **Explore Lost Time** - RAG-based passage retrieval from Proust's text
2. **Reflect on My Day** - Introspective conversation in Proust's style

## Commands

### Frontend (from project root)
```bash
npm install          # Install dependencies
npm run dev          # Start Vite dev server (localhost:5173)
npm run build        # TypeScript compile + Vite build
npm run preview      # Preview production build
```

### Backend (from backend/ directory)
```bash
python3 -m venv venv && source venv/bin/activate  # Create/activate venv
pip install -r requirements.txt                    # Install dependencies
python -m spacy download en_core_web_sm            # Download NLP model
cp .env.example .env                               # Create env file
# Edit .env with your PINECONE_API_KEY, GROQ_API_KEY, and COHERE_API_KEY
python server.py                                    # Start server (localhost:5000)
# or: uvicorn server:app --host 127.0.0.1 --port 5000
```

### Data Sanitization & Ingestion (one-time setup)
```bash
cd backend
python scripts/sanitize_passages.py  # Clean parsed.json → parsed_clean.json (EN-only, legacy)

# Bilingual pipeline (preferred):
python scripts/download_english_corpus.py  # Download EN from Standard Ebooks + PG AU
python scripts/download_french_corpus.py   # Download FR from Wikisource
python scripts/align_sentences.py --test   # Test on Vol 1 Overture first
pytest tests/test_alignment.py -k integration  # Verify test output quality
python scripts/align_sentences.py          # Full sentence-level alignment → parsed_clean_bilingual.json
python scripts/verify_alignment.py         # Quality checks
python scripts/ingest_pinecone.py          # Ingest to Pinecone (proust-index-v2)
```

### Testing
```bash
# Health check
curl http://127.0.0.1:5000/health

# Test streaming RAG
curl -N -X POST http://127.0.0.1:5000/api/explore_lost_time/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "madeleine memory"}'

# Test non-streaming (backward compat)
curl -X POST http://127.0.0.1:5000/api/explore_lost_time \
  -H "Content-Type: application/json" \
  -d '{"query": "madeleine memory"}'

python backend/test_metadata.py  # Run backend tests

# RAG evaluation
cd backend
python scripts/evaluate.py              # Full eval with LLM-as-judge
python scripts/evaluate.py --fast       # Retrieval metrics only (faster)
python scripts/evaluate.py -n 5 -v      # First 5 questions, verbose
python scripts/evaluate.py --export results.json  # Export to JSON
```

## Architecture

```
src/                    # React frontend (Vite + TypeScript)
├── App.tsx             # Routes: / → LandingPage, /chat → ChatPage, /about → AboutPage
├── ChatPage.tsx        # Main chat interface with streaming support
├── LandingPage.tsx
├── AboutPage.tsx
├── components/
│   └── PassageDisplay.tsx
├── hooks/
│   ├── useStreamingQuery.ts  # SSE streaming hook for real-time responses
│   └── useLocalStorage.ts
└── styles/theme.ts     # Centralized theme (browns/creams palette)

backend/                # FastAPI + Python
├── server.py           # Main API with streaming + non-streaming endpoints (FastAPI)
├── config.py           # Centralized configuration (Pydantic BaseSettings)
├── retrieval.py        # LangChain orchestration (Groq LLM, Cohere embeddings/rerank, RAG)
├── text_utils.py       # Shared text cleaning (OCR artifact fixes)
├── metadata.py         # Metadata extraction (characters, themes, reading time)
├── connection_mapper.py # Semantic relationship building
├── evaluation.py       # RAG evaluation metrics (precision, recall, faithfulness)
├── scripts/
│   ├── sanitize_passages.py  # Clean & re-chunk parsed.json → parsed_clean.json
│   ├── download_english_corpus.py  # Download EN from Standard Ebooks + PG Australia
│   ├── download_french_corpus.py   # Download FR from Wikisource
│   ├── align_sentences.py           # Sentence-level bilingual alignment (Cohere + DP)
│   ├── verify_alignment.py         # Alignment quality verification
│   ├── ingest_pinecone.py    # Data ingestion to Pinecone (supports bilingual)
│   └── evaluate.py           # CLI runner for evaluation suite
├── .env.example        # Environment variable template
├── parsed_clean_bilingual.json  # Bilingual passages (~12,924 passages, EN + FR)
├── parsed_clean.json   # Sanitized EN-only passages (~12,764 passages, legacy)
└── reading_paths.json  # Guided reading paths
```

## Key Technical Details

### RAG Pipeline (LangChain + Groq + Cohere + Pinecone)

The RAG system uses LangChain for orchestration with API-based services:
1. **Retrieval** - Pinecone vector search (k=20 candidates)
2. **Reranking** - Cohere `rerank-v3.5` (narrows to top 5)
3. **Embedding** - Cohere `embed-v4.0` (1536 dimensions)
4. **Generation** - Groq API with Kimi K2 (`moonshotai/kimi-k2-instruct`, 131K context)

### Models
- **Embedding:** Cohere `embed-v4.0` (1536-dim, via langchain-cohere CohereEmbeddings)
- **LLM:** Groq API with Kimi K2 via langchain-groq ChatGroq (streaming supported)
- **Reranker:** Cohere `rerank-v3.5` (two-stage retrieval for better relevance)
- **Vector DB:** Pinecone (serverless, cosine similarity, 1536-dim index)
- **NLP:** spaCy `en_core_web_sm` for entity extraction

### API Endpoints

**Streaming (SSE):**
- `POST /api/explore_lost_time/stream` - Streaming RAG with token-by-token response
- `POST /api/reflect/stream` - Streaming reflection conversation

**Non-Streaming (backward compatible):**
- `POST /api/explore_lost_time` - RAG retrieval, returns `{passages: [...], reply: "..."}`
- `POST /api/reflect` - Introspective response, returns `{reply: "..."}`

**Health:**
- `GET /health` - Health check with Pinecone/LLM status

### SSE Event Format
```json
{"type": "token", "token": "..."}      // Individual tokens
{"type": "sources", "passages": [...]} // Source passages (RAG only)
{"type": "done", "done": true}         // Stream complete
{"type": "error", "error": "..."}      // Error message
```

### Configuration

Environment variables (see `backend/.env.example`):
```
PINECONE_API_KEY      # Required - Pinecone API key
GROQ_API_KEY          # Required - Groq API key (https://console.groq.com/)
COHERE_API_KEY        # Required - Cohere API key (https://dashboard.cohere.com/)
PINECONE_INDEX_NAME   # Default: "proust-index" (use "proust-index-v2" for bilingual)
LLM_MODEL_NAME        # Default: "moonshotai/kimi-k2-instruct"
RETRIEVAL_K           # Default: 5 (final passages returned)
RETRIEVAL_CANDIDATES  # Default: 20 (candidates fetched before reranking)
```

## Styling Conventions

- **Styled-components** with transient props (`$propName`)
- **Theme colors:** `#8b4513` (saddle brown), `#f7f4f0` (cream), `#333` (text)
- **Fonts:** Belgrano (headings), Georgia (body), IBM Plex Sans (sans-serif)

## Work in Progress

- Combray gallery page
