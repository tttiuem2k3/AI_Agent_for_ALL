# -*- coding: utf-8 -*-
"""Vector-store protocol types for additive RAG support."""
from abc import ABC, abstractmethod
from typing import Any, Self

from pydantic import BaseModel, Field

from ._document import Chunk


class VectorRecord(BaseModel):
    vector: list[float]
    document_id: str
    chunk: Chunk


class VectorSearchResult(BaseModel):
    score: float
    document_id: str
    chunk: Chunk


class DocumentSummary(BaseModel):
    document_id: str
    source: str
    chunk_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class VectorStoreBase(ABC):
    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        return None

    @abstractmethod
    async def create_collection(self, name: str, dimensions: int) -> None:
        """Create a collection."""

    @abstractmethod
    async def delete_collection(self, name: str) -> None:
        """Delete a collection."""

    @abstractmethod
    async def has_collection(self, name: str) -> bool:
        """Return whether a collection exists."""

    @abstractmethod
    async def insert(self, collection: str, records: list[VectorRecord]) -> None:
        """Insert records."""

    @abstractmethod
    async def delete(self, collection: str, document_id: str) -> None:
        """Delete all chunks for one document."""

    @abstractmethod
    async def search(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int = 5,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        """Search similar vectors."""

    @abstractmethod
    async def list_documents(
        self,
        collection: str,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[DocumentSummary]:
        """List source documents indexed in one collection."""
