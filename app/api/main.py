from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import agent, collections, health, ingest, query, stats, system
from app.core.config import settings
from app.core.logging import configure_logging

configure_logging()

app = FastAPI(
    title="DCLAW RAG",
    description="Retrieval-Augmented Generation API",
    version="0.1.0",
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
app.include_router(query.router, prefix="/api/v1/rag", tags=["Query"])
app.include_router(agent.router, prefix="/api/v1/rag", tags=["Agent"])
app.include_router(collections.router, prefix="/api/v1/rag", tags=["Collections"])
app.include_router(ingest.router, prefix="/api/v1/rag/documents", tags=["Documents"])
