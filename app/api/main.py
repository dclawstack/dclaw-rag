from fastapi import FastAPI

from app.api.routes import collections, health, ingest, query
from app.core.config import settings
from app.core.logging import configure_logging

configure_logging()

app = FastAPI(
    title="DCLAW RAG",
    description="Retrieval-Augmented Generation API",
    version="0.1.0",
)

app.include_router(health.router, tags=["Health"])
app.include_router(query.router, prefix="/api/v1/rag", tags=["Query"])
app.include_router(collections.router, prefix="/api/v1/rag", tags=["Collections"])
app.include_router(ingest.router, prefix="/api/v1/rag/documents", tags=["Documents"])
