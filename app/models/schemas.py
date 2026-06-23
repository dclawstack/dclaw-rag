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
    collection_id: str | None = None


class DocumentChunk(BaseModel):
    id: UUID
    text: str
    embedding: list[float] | None = None
    score: float | None = None
    metadata: ChunkMetadata


class IngestRequest(BaseModel):
    source: str
    title: str | None = None
    tags: list[str] = Field(default_factory=list)
    tenant_id: str | None = None
    collection_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestResponse(BaseModel):
    doc_id: UUID
    chunks_inserted: int
    status: str


class TextIngestRequest(BaseModel):
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class QueryRequest(BaseModel):
    question: str
    top_k: int = 10
    tenant_id: str | None = None
    collection_id: str | None = None
    rewrite_query: bool = False
    filters: dict[str, Any] = Field(default_factory=dict)


class RetrievedChunk(BaseModel):
    id: UUID
    chunk_id: str
    text: str
    score: float
    document_name: str
    metadata: ChunkMetadata


class Citation(BaseModel):
    index: int
    chunk_id: str
    text: str
    source: str
    page: int | None = None


class QueryResponse(BaseModel):
    query: str
    answer: str
    results: list[RetrievedChunk]
    retrieved_chunks: list[RetrievedChunk]
    citations: list[Citation]
    confidence: str = "medium"
    latency_ms: float


class CollectionCreate(BaseModel):
    name: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)


class Collection(BaseModel):
    id: str
    name: str
    description: str | None = None
    document_count: int = 0
    chunk_count: int = 0
    status: str = "ready"
    tags: list[str] = Field(default_factory=list)
    created_at: str


class Document(BaseModel):
    id: str
    filename: str
    status: str = "ready"
    created_at: str = ""


class HealthResponse(BaseModel):
    status: str
    version: str = "0.1.0"
