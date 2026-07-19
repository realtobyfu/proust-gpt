# ============================================================
# Stage 1: Build the React frontend
# ============================================================
FROM node:20-alpine AS frontend

WORKDIR /build

COPY package.json package-lock.json* ./
RUN npm ci

COPY tsconfig.json vite.config.ts ./
COPY src/ src/
COPY public/ public/
COPY index.html ./

RUN npm run build

# ============================================================
# Stage 2: Python backend + built frontend
# ============================================================
FROM python:3.11-slim

# curl is used by the healthcheck below
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies. Note: spaCy's en_core_web_sm model is NOT
# downloaded here — the serving path (server/retrieval/agent/corpus) never
# imports spaCy; entity extraction lives in offline preprocessing scripts (K2).
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ ./

# Copy built frontend into /app/static
COPY --from=frontend /build/dist ./static

# Production defaults
ENV SERVE_STATIC=true
ENV STATIC_DIR=./static
ENV PORT=8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

EXPOSE ${PORT}

# Use sh -c so $PORT is expanded at runtime (Render sets PORT)
CMD sh -c "uvicorn server:app --host 0.0.0.0 --port ${PORT}"
