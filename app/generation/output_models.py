from uuid import UUID

from pydantic import BaseModel, Field


class CitationOutput(BaseModel):
    answer: str = Field(..., description="The generated answer")
    citations: list[int] = Field(default_factory=list, description="Indices of cited context chunks")
    confidence: str = Field(default="medium", description="high | medium | low")


class GeneratedAnswer(BaseModel):
    answer: str
    citations: list[int]
    confidence: str
    retrieved_chunk_ids: list[UUID]
