from fastapi import Depends, Header, HTTPException, Request

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.api_key_store import ApiKeyStore
from app.db.collection_store import CollectionStore
from app.db.document_store import DocumentStore
from app.db.qdrant_store import QdrantStore
from app.db.rate_limiter import RateLimiter
from app.db.user_store import UserStore
from app.generation.llm_gateway import LLMGateway, get_llm_gateway
from app.ingestion.pipeline import IngestionPipeline
from app.retrieval.search import Searcher


async def get_searcher(request: Request) -> Searcher:
    if not hasattr(request.app.state, "searcher"):
        request.app.state.searcher = Searcher()
    return request.app.state.searcher


async def get_pipeline(request: Request) -> IngestionPipeline:
    if not hasattr(request.app.state, "pipeline"):
        request.app.state.pipeline = IngestionPipeline()
    return request.app.state.pipeline


async def get_llm(request: Request) -> LLMGateway:
    if not hasattr(request.app.state, "llm"):
        request.app.state.llm = get_llm_gateway()
    return request.app.state.llm


async def get_store(request: Request) -> QdrantStore:
    if not hasattr(request.app.state, "store"):
        request.app.state.store = QdrantStore()
    return request.app.state.store


async def get_collection_store(request: Request) -> CollectionStore:
    if not hasattr(request.app.state, "collection_store"):
        request.app.state.collection_store = CollectionStore()
    return request.app.state.collection_store


async def get_api_key_store(request: Request) -> ApiKeyStore:
    if not hasattr(request.app.state, "api_key_store"):
        request.app.state.api_key_store = ApiKeyStore()
    return request.app.state.api_key_store


async def get_document_store(request: Request) -> DocumentStore:
    if not hasattr(request.app.state, "document_store"):
        request.app.state.document_store = DocumentStore()
    return request.app.state.document_store


async def get_user_store(request: Request) -> UserStore:
    if not hasattr(request.app.state, "user_store"):
        request.app.state.user_store = UserStore()
    return request.app.state.user_store


class Principal:
    """The authenticated caller — an end user (JWT) or a machine (API key)."""

    def __init__(
        self,
        tenant_id: str,
        key_name: str = "",
        user_id: str | None = None,
        email: str | None = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.key_name = key_name
        self.user_id = user_id
        self.email = email


async def get_principal(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    store: ApiKeyStore = Depends(get_api_key_store),
) -> Principal:
    raw = None
    if authorization and authorization.lower().startswith("bearer "):
        raw = authorization[7:].strip()
    elif x_api_key:
        raw = x_api_key.strip()
    if not raw:
        raise HTTPException(status_code=401, detail="Missing credentials")

    # A Bearer token may be a user JWT or a machine API key — try JWT first.
    claims = decode_access_token(raw)
    if claims:
        return Principal(
            tenant_id=claims["tenant_id"],
            user_id=claims.get("sub"),
            email=claims.get("email"),
        )

    record = store.get(raw)
    if record:
        return Principal(tenant_id=record["tenant_id"], key_name=record.get("name", ""))

    raise HTTPException(status_code=401, detail="Invalid or expired credentials")


async def get_rate_limiter(request: Request) -> RateLimiter:
    if not hasattr(request.app.state, "rate_limiter"):
        request.app.state.rate_limiter = RateLimiter()
    return request.app.state.rate_limiter


async def enforce_rate_limit(
    principal: Principal = Depends(get_principal),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> None:
    """Guard dependency: 429s the tenant when over the per-minute limit."""
    allowed, retry_after = limiter.check(principal.tenant_id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def enforce_auth_rate_limit(
    request: Request,
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> None:
    """Guard for the unauthenticated auth endpoints: rate-limit by client IP."""
    allowed, retry_after = limiter.check(
        f"auth:{_client_ip(request)}", limit=settings.auth_rate_limit_per_minute
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many attempts; try again shortly",
            headers={"Retry-After": str(retry_after)},
        )
