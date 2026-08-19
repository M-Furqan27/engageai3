from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ExtractedDocument(BaseModel):
    source_type: str
    source_name: str
    section: Optional[str] = None
    content: str


class Chunk(BaseModel):
    source_type: str
    source_name: str
    section: Optional[str] = None
    chunk_index: int
    text: str


class EmbeddedChunk(BaseModel):
    source_type: str
    source_name: str
    section: Optional[str] = None
    chunk_index: int
    text: str
    embedding: List[float]


class KnowledgeSource(BaseModel):
    source_type: str
    source_name: str
    chunks: List[EmbeddedChunk]


class KnowledgeBase(BaseModel):
    organization_id: str
    sources: List[KnowledgeSource]


class ManualKnowledgeCreate(BaseModel):
    organization_id: UUID
    title: str = Field(min_length=1, max_length=180)
    content: str = Field(min_length=1)

    @field_validator("title", "content")
    @classmethod
    def trim(cls, value: str):
        return value.strip()
