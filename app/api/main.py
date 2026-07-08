from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware import (
    BodySizeLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from app.api.routes import (
    agent,
    auth,
    collections,
    health,
    ingest,
    keys,
    query,
    stats,
    system,
    transcribe,
    usage,
)
from app.core.config import settings, validate_runtime_config
from app.core.exceptions import GenerationError, IngestionError, RetrievalError
from app.core.logging import configure_logging
from app.db.api_key_store import ApiKeyStore

configure_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast on an insecure/incomplete production configuration.
    if settings.app_env == "production":
        problems = validate_runtime_config(settings)
        if problems:
            for problem in problems:
                logger.error("config_invalid", problem=problem)
            raise RuntimeError("Invalid production configuration: " + "; ".join(problems))

    # Seed the bootstrap API key so the dev frontend has a working credential.
    if settings.bootstrap_api_key:
        try:
            ApiKeyStore().ensure_key(
                settings.bootstrap_api_key, settings.bootstrap_tenant, "bootstrap"
            )
            logger.info("bootstrap_api_key_seeded", tenant=settings.bootstrap_tenant)
        except Exception as exc:  # Redis may be unavailable at startup
            logger.warning("bootstrap_api_key_seed_failed", error=str(exc))
    yield


app = FastAPI(
    title="DCLAW RAG",
    description="Retrieval-Augmented Generation API",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(IngestionError)
async def ingestion_error_handler(request, exc: IngestionError):
    """Client-caused ingestion problems (unsupported type, empty text) are 422s,
    not 500s."""
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(GenerationError)
@app.exception_handler(RetrievalError)
async def upstream_error_handler(request, exc: Exception):
    """LLM/vector-store failures are upstream problems: return a real 502 with
    the reason (an unhandled exception would also lose its CORS headers, which
    browsers report as an opaque CORS error instead of the actual cause)."""
    logger.error("upstream_dependency_failed", error=str(exc))
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=502, content={"detail": str(exc)})

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(BodySizeLimitMiddleware)
# Added last so it is outermost: it times the whole request and tags every log.
app.add_middleware(RequestContextMiddleware)

app.include_router(health.router, tags=["Health"])
app.include_router(system.router, prefix="/api/v1/rag", tags=["System"])
app.include_router(stats.router, prefix="/api/v1/rag", tags=["System"])
app.include_router(usage.router, prefix="/api/v1/rag", tags=["System"])
app.include_router(auth.router, prefix="/api/v1/rag", tags=["Auth"])
app.include_router(keys.router, prefix="/api/v1/rag", tags=["Auth"])
app.include_router(query.router, prefix="/api/v1/rag", tags=["Query"])
app.include_router(transcribe.router, prefix="/api/v1/rag", tags=["Query"])
app.include_router(agent.router, prefix="/api/v1/rag", tags=["Agent"])
app.include_router(collections.router, prefix="/api/v1/rag", tags=["Collections"])
app.include_router(ingest.router, prefix="/api/v1/rag/documents", tags=["Documents"])
