from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Dense vector size per embedding model — the Qdrant collection dimension is
# fixed at creation, so this must match the configured model.
_EMBEDDING_DIMS = {
    "BAAI/bge-large-en-v1.5": 1024,
    "BAAI/bge-base-en-v1.5": 768,
    "BAAI/bge-small-en-v1.5": 384,
}


class Settings(BaseSettings):
    app_env: str = "dev"
    log_level: str = "INFO"

    # server: Redis + external Qdrant + Celery (the default, for deployments).
    # local: zero external services — SQLite KV, embedded Qdrant, inline
    # ingestion — for running as a single desktop process.
    app_mode: str = "server"  # server | local
    data_dir: str = "~/.dclaw-rag"  # local-mode state root (SQLite + Qdrant files)

    # Encryption at rest for local-mode state (SQLite KV via SQLCipher whole-DB;
    # Qdrant chunk text via Fernet). Off by default — server deployments rely on
    # infrastructure disk/volume encryption. Turn it on for regulated/local-first
    # users. Needs the 'encryption' extra. Enabling on an EXISTING plaintext store
    # requires a fresh store (SQLCipher can't open an unencrypted DB) — losing the
    # key loses the data. Either set encryption_key directly, or set
    # encryption_key_file=True to load/generate a key at data_dir/encryption.key.
    encryption_key: str | None = None
    encryption_key_file: bool = False

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

    # Speech-to-text (audio ingestion + voice queries), lazy-loaded on first
    # use. Any faster-whisper size/id works (tiny/base/small/...).
    whisper_model: str = "base"

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "dclaw_docs"
    qdrant_api_key: str | None = None

    llm_provider: str = "openai"  # openai | anthropic | openrouter | ollama | local
    llm_model: str = "gpt-4o-mini"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    # Bundled local LLM (llama.cpp, in-process GGUF — no daemon, no network at
    # inference). The model file is downloaded from Hugging Face once on first
    # use (cached under data_dir/models) unless local_llm_model_path points at an
    # existing .gguf. This is the fully-local answer engine — pair with local
    # embeddings + whisper for an offline install.
    local_llm_model_repo: str = "bartowski/Qwen2.5-3B-Instruct-GGUF"
    local_llm_model_file: str = "Qwen2.5-3B-Instruct-Q4_K_M.gguf"
    local_llm_model_path: str | None = None  # explicit .gguf; skips the HF download
    local_llm_n_ctx: int = 4096
    local_llm_n_threads: int | None = None  # None -> llama.cpp picks a default
    local_llm_max_tokens: int = 2048

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

    # Retrieval quality (E2).
    # Contextual retrieval: prepend document context (title/source) to each chunk
    # before embedding so its vector captures where it sits in the document —
    # a recall win, no LLM. Affects newly-ingested docs only; stored text is
    # unchanged, so it's safe to toggle and mix with existing chunks.
    contextual_retrieval: bool = True
    # Self-correcting retrieval: when the top reranked score is weak, reformulate
    # the query once with the LLM and re-retrieve before answering/abstaining.
    self_correct_retrieval: bool = True
    self_correct_threshold: float = 0.5  # reformulate below this rerank score
    # Agentic RAG: after the initial decomposition, reflect on the gathered
    # evidence and issue follow-up searches until the question is covered or the
    # step budget (AgentRequest.max_steps) is spent.
    agentic_reflection: bool = True

    # Visual-document ingestion (E3, needs the 'vision' extra: pdfplumber +
    # pytesseract + Pillow + pymupdf, plus the system `tesseract` binary for OCR).
    # All lazy — the non-visual path never loads them. Tables are pulled out of
    # PDFs; PDFs with little/no extractable text (scanned) are OCR'd, as are
    # image uploads (png/jpg/tiff/...).
    extract_tables: bool = True
    ocr_scanned_pdfs: bool = True
    ocr_min_chars: int = 100  # below this many extracted chars a PDF is treated as scanned

    # Trust & observability (E4).
    # Flag retrieved chunks whose document is older than this many days (0 = off).
    stale_after_days: int = 365
    # LLM-check the retrieved sources for contradictions (one extra call, only
    # when >= 2 distinct sources are retrieved on the answer path).
    flag_contradictions: bool = True

    # LLM pricing for usage/cost metering (USD per 1K tokens). Defaults are
    # Sonnet-tier; set these to match your configured model/provider.
    llm_price_per_1k_input_usd: float = 0.003
    llm_price_per_1k_output_usd: float = 0.015

    # Trust controls: abstain when the top reranked chunk scores below this
    # (cross-encoder relevance in [0,1]; relevant hits score ~0.7-1.0, irrelevant
    # ~0.0), and verify answers against their sources.
    abstain_threshold: float = 0.2
    verify_answers: bool = True

    # Per-tenant query response cache TTL (seconds); 0 disables. Invalidated
    # immediately when the tenant ingests a document (cache version bump).
    query_cache_ttl_seconds: int = 300

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"

    # Abuse / resource limits.
    rate_limit_per_minute: int = 60  # per tenant, on the costly endpoints; 0 disables
    auth_rate_limit_per_minute: int = 10  # per client IP, on register/login; 0 disables
    max_upload_bytes: int = 10 * 1024 * 1024  # 10 MiB per uploaded file
    max_request_bytes: int = 12 * 1024 * 1024  # global request body cap

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @model_validator(mode="after")
    def _apply_local_profile(self) -> "Settings":
        """Local-mode defaults; anything set explicitly (env/.env) wins."""
        if self.app_mode == "local":
            if "rate_limit_per_minute" not in self.model_fields_set:
                self.rate_limit_per_minute = 0  # single user, no abuse surface
            if "embedding_model" not in self.model_fields_set:
                self.embedding_model = "BAAI/bge-small-en-v1.5"
            if "bootstrap_api_key" not in self.model_fields_set:
                self.bootstrap_api_key = "sk_local"  # the local frontend's NEXT_PUBLIC_API_KEY
        return self

    @property
    def embedding_dim(self) -> int:
        return _EMBEDDING_DIMS.get(self.embedding_model, 1024)

    @property
    def sqlite_path(self) -> Path:
        return Path(self.data_dir).expanduser() / "kv.sqlite3"

    @property
    def qdrant_path(self) -> Path:
        return Path(self.data_dir).expanduser() / "qdrant"

    @property
    def local_llm_dir(self) -> Path:
        return Path(self.data_dir).expanduser() / "models"

    @property
    def encryption_key_path(self) -> Path:
        return Path(self.data_dir).expanduser() / "encryption.key"


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
