from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ChunkMetadata(BaseModel):
    doc_id: UUID
    chunk_index: int
    parent_id: UUID | None = None
    source: str
    title: str | None = None
    created_at: datetime | None = None
    tags: list[str] = Field(default_factory=list)
    checksum: str | None = None
    tenant_id: str | None = None


class DocumentChunk(BaseModel):
    id: UUID
    text: str
    embedding: list[float] | None = None
    metadata: ChunkMetadata


class IngestRequest(BaseModel):
    source: str
    title: str | None = None
    tags: list[str] = Field(default_factory=list)
    tenant_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestResponse(BaseModel):
    doc_id: UUID
    chunks_inserted: int
    status: str


class QueryRequest(BaseModel):
    question: str
    top_k: int = 10
    tenant_id: str | None = None
    rewrite_query: bool = False
    filters: dict[str, Any] = Field(default_factory=dict)


class RetrievedChunk(BaseModel):
    id: UUID
    text: str
    score: float
    metadata: ChunkMetadata


class Citation(BaseModel):
    index: int
    chunk_id: UUID
    source: str


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    confidence: str = "medium"
    retrieved_chunks: list[RetrievedChunk]


class HealthResponse(BaseModel):
    status: str
    version: str = "0.1.0"
