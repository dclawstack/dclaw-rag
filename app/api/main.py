from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import agent, collections, health, ingest, keys, query, stats, system
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.api_key_store import ApiKeyStore

configure_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["Health"])
app.include_router(system.router, prefix="/api/v1/rag", tags=["System"])
app.include_router(stats.router, prefix="/api/v1/rag", tags=["System"])
app.include_router(keys.router, prefix="/api/v1/rag", tags=["Auth"])
app.include_router(query.router, prefix="/api/v1/rag", tags=["Query"])
app.include_router(agent.router, prefix="/api/v1/rag", tags=["Agent"])
app.include_router(collections.router, prefix="/api/v1/rag", tags=["Collections"])
app.include_router(ingest.router, prefix="/api/v1/rag/documents", tags=["Documents"])
