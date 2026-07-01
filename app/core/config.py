from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "dev"
    log_level: str = "INFO"

    api_host: str = "0.0.0.0"
    api_port: int = 8090

    cors_allow_origins: list[str] = ["http://localhost:3003"]

    # Auth: API key -> tenant. bootstrap_api_key is seeded on startup (used by the
    # dev frontend); admin_api_key is required to mint new tenant keys.
    bootstrap_api_key: str | None = None
    bootstrap_tenant: str = "default"
    admin_api_key: str | None = None

    # End-user auth (email+password -> JWT). jwt_secret signs the tokens.
    # Access tokens are short-lived and stateless; refresh tokens are long-lived,
    # stored in Redis, and revocable (logout / rotation / revoke-all).
    jwt_secret: str = "dev-insecure-jwt-secret-change-me"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 30

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

    # Abuse / resource limits.
    rate_limit_per_minute: int = 60  # per tenant, on the costly endpoints; 0 disables
    auth_rate_limit_per_minute: int = 10  # per client IP, on register/login; 0 disables
    max_upload_bytes: int = 10 * 1024 * 1024  # 10 MiB per uploaded file
    max_request_bytes: int = 12 * 1024 * 1024  # global request body cap

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()

# Dev placeholders that must never reach production.
_DEV_KEYS = {"sk_dev_bootstrap", "sk_admin_dev"}
_DEV_JWT_SECRET = "dev-insecure-jwt-secret-change-me"

# API key required by the LLM provider (ollama is local, needs none).
_PROVIDER_KEY = {
    "openai": "openai_api_key",
    "anthropic": "anthropic_api_key",
    "openrouter": "openrouter_api_key",
}


def validate_runtime_config(s: Settings) -> list[str]:
    """Return a list of misconfigurations that must block a production start.

    Empty list means OK. Only enforced when app_env == 'production' (the caller
    decides); in dev these are non-fatal conveniences.
    """
    problems: list[str] = []

    if not s.admin_api_key:
        problems.append("ADMIN_API_KEY is not set (key minting would be wide open)")
    if s.admin_api_key in _DEV_KEYS or s.bootstrap_api_key in _DEV_KEYS:
        problems.append("A dev placeholder API key is in use; set real secrets")
    if "*" in s.cors_allow_origins:
        problems.append("CORS_ALLOW_ORIGINS is a wildcard '*'")
    if s.jwt_secret == _DEV_JWT_SECRET or len(s.jwt_secret) < 32:
        problems.append("JWT_SECRET is the dev default or too short (set a strong secret)")

    key_field = _PROVIDER_KEY.get(s.llm_provider)
    if key_field and not getattr(s, key_field):
        problems.append(
            f"LLM provider '{s.llm_provider}' selected but {key_field.upper()} is unset"
        )

    return problems
