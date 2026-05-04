from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "dev"
    log_level: str = "INFO"

    api_host: str = "0.0.0.0"
    api_port: int = 8090

    embedding_model: str = "BAAI/bge-large-en-v1.5"
    embedding_device: str = "cpu"
    embedding_batch_size: int = 32

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "dclaw_docs"
    qdrant_api_key: str | None = None

    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    reranker_model: str = "BAAI/bge-reranker-base"
    reranker_top_k: int = 10

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
