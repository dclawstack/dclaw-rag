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
    sparse_embedding: dict[str, Any] | None = None
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
    verify: bool = True
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
    abstained: bool = False
    faithfulness: str | None = None  # "grounded" | "partial" | "unsupported" | None
    unsupported_claims: list[str] = Field(default_factory=list)
    latency_ms: float


class AgentRequest(BaseModel):
    question: str
    top_k: int = 5
    max_steps: int = 4
    tenant_id: str | None = None
    collection_id: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)


class AgentStep(BaseModel):
    sub_question: str
    n_results: int


class AgentResponse(BaseModel):
    query: str
    answer: str
    citations: list[Citation]
    retrieved_chunks: list[RetrievedChunk]
    confidence: str = "medium"
    steps: list[AgentStep]
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
    chunk_count: int = 0
    error: str | None = None


class HealthResponse(BaseModel):
    status: str
    version: str = "0.1.0"


class SystemInfo(BaseModel):
    version: str = "0.1.0"
    backend_port: int
    vector_store: str = "Qdrant"
    embedding_model: str
    reranker_model: str
    llm_provider: str
    llm_model: str


class Stats(BaseModel):
    collections: int
    documents: int
    chunks: int


class ApiKeyCreate(BaseModel):
    tenant_id: str
    name: str = ""


class ApiKeyResponse(BaseModel):
    api_key: str
    tenant_id: str
    name: str
