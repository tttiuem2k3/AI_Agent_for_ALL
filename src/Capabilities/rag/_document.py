# -*- coding: utf-8 -*-
"""RAG document structures."""
from typing import Any

from pydantic import BaseModel, Field

from Runtime.message import DataBlock, TextBlock


class Section(BaseModel):
    """A natural section produced by a parser."""

    content: TextBlock | DataBlock
    source: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class Chunk(BaseModel):
    """A final indexable chunk."""

    content: TextBlock | DataBlock
    source: str
    chunk_index: int
    total_chunks: int
    metadata: dict[str, Any] = Field(default_factory=dict)
