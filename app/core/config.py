from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "dev"
    log_level: str = "INFO"

    api_host: str = "0.0.0.0"
    api_port: int = 8090

    cors_allow_origins: list[str] = ["*"]

    embedding_model: str = "BAAI/bge-large-en-v1.5"
    embedding_device: str = "cpu"
    embedding_batch_size: int = 32

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "dclaw_docs"
    qdrant_api_key: str | None = None

    llm_provider: str = "openai"  # openai | anthropic | openrouter | ollama
    llm_model: str = "gpt-4o-mini"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    # OpenRouter (OpenAI-compatible gateway to many hosted models)
    openrouter_api_key: str | None = None
    openrouter_model: str = "openai/gpt-4o-mini"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    llm_fallback_to_ollama: bool = True

    sparse_model: str = "Qdrant/bm25"
    hybrid_candidate_k: int = 100
    rrf_k: int = 60

    reranker_model: str = "BAAI/bge-reranker-base"
    reranker_top_k: int = 10

    # Trust controls: abstain when the top reranked chunk scores below this
    # (cross-encoder relevance in [0,1]; relevant hits score ~0.7-1.0, irrelevant
    # ~0.0), and verify answers against their sources.
    abstain_threshold: float = 0.2
    verify_answers: bool = True

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
