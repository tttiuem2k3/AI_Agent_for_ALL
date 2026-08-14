# -*- coding: utf-8 -*-
"""Contracts for document conversion implementations."""
from __future__ import annotations

from typing import Any, Protocol


class DocumentConversionBackend(Protocol):
    """Private backend contract consumed by the public service."""

    def format_from_bytes(self, data: bytes) -> str | None: ...

    def format_from_extension(self, extension: str) -> str | None: ...

    def to_markdown_bytes(self, data: bytes, format_name: str | None) -> str: ...

    def to_document(self, data: bytes, format_name: str | None) -> Any: ...
