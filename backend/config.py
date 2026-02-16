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
    PINECONE_INDEX_NAME: str = "proust-index"

    # Groq LLM settings
    GROQ_API_KEY: str = ""
    LLM_MODEL_NAME: str = "moonshotai/kimi-k2-instruct"
    LLM_TEMPERATURE: float = 0.6
    LLM_MAX_TOKENS: int = 800
    LLM_FREQUENCY_PENALTY: float = 0.6

    # Cohere settings
    COHERE_API_KEY: str = ""
    COHERE_EMBED_MODEL: str = "embed-v4.0"
    COHERE_RERANK_MODEL: str = "rerank-v3.5"
    RERANK_TOP_N: int = 5

    # App settings
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    DEBUG: bool = True
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    SERVE_STATIC: bool = False
    STATIC_DIR: str = "./static"
    PORT: int = 5000

    # Embedding settings
    EMBEDDING_DIMENSION: int = 1536

    # RAG settings
    RETRIEVAL_K: int = 5
    RETRIEVAL_CANDIDATES: int = 20

    # Agent settings
    AGENT_ENABLED: bool = True
    REFLECT_AGENT_ENABLED: bool = True
    AGENT_MAX_STEPS: int = 4

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
