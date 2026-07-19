"""
Centralized configuration for ProustGPT backend.
Uses Pydantic BaseSettings to load and validate environment variables.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Pinecone settings
    PINECONE_API_KEY: str = ""
    PINECONE_INDEX_NAME: str = "proust-index-v3"

    # Groq LLM settings
    GROQ_API_KEY: str = ""
    LLM_MODEL_NAME: str = "llama-3.3-70b-versatile"
    LLM_TEMPERATURE: float = 0.6
    LLM_MAX_TOKENS: int = 800
    LLM_FREQUENCY_PENALTY: float = 0.6

    # Cohere settings
    COHERE_API_KEY: str = ""
    COHERE_EMBED_MODEL: str = "embed-v4.0"
    COHERE_RERANK_MODEL: str = "rerank-v3.5"
    RERANK_TOP_N: int = 5

    # App settings
    DEBUG: bool = False
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    SERVE_STATIC: bool = False
    STATIC_DIR: str = "./static"
    PORT: int = 5000

    # Embedding settings
    EMBEDDING_DIMENSION: int = 1536

    # RAG settings
    RETRIEVAL_K: int = 5
    RETRIEVAL_CANDIDATES: int = 20

    # Request / input limits (security hardening — B2)
    MAX_QUERY_CHARS: int = 2000        # max length of a single query/message
    MAX_HISTORY_TURNS: int = 12        # server-side cap on replayed history turns

    # Rate limiting (B1) — per-IP, applied to chat endpoints
    RATE_LIMIT_ENABLED: bool = True
    CHAT_RATE_LIMIT: str = "10/minute"
    READ_RATE_LIMIT: str = "60/minute"

    # External-call reliability (E3) — seconds
    GROQ_TIMEOUT: float = 60.0
    GROQ_MAX_RETRIES: int = 2
    COHERE_TIMEOUT: float = 30.0
    HEALTH_STATS_TTL: int = 300        # cache /health Pinecone stats for N seconds (E2)
    RETRIEVAL_CACHE_TTL: int = 300     # cache (query, lang) retrieval results (E1)
    RETRIEVAL_CACHE_SIZE: int = 256

    # SSE executor sizing (E4)
    SSE_MAX_WORKERS: int = 8

    # Agent settings
    AGENT_ENABLED: bool = True
    REFLECT_AGENT_ENABLED: bool = True
    AGENT_MAX_STEPS: int = 4
    AGENT_TEMPERATURE: float = 0.2     # lower temp for tool-calling reliability (A8)
    AGENT_TIMEOUT: float = 90.0        # overall wall-clock cap on an agent run (D2)

    # LangSmith tracing (opt-in)
    LANGCHAIN_TRACING_V2: bool = False
    LANGSMITH_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "proust-gpt"

    def validate(self) -> list[str]:
        """
        Validate that required configuration is present.
        Returns a list of missing required config keys.
        """
        missing = []
        if not self.PINECONE_API_KEY:
            missing.append("PINECONE_API_KEY")
        if not self.GROQ_API_KEY:
            missing.append("GROQ_API_KEY")
        if not self.COHERE_API_KEY:
            missing.append("COHERE_API_KEY")
        return missing

    def is_valid(self) -> bool:
        """Check if all required configuration is present."""
        return len(self.validate()) == 0


# Singleton instance
config = Config()
