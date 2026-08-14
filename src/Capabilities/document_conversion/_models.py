# -*- coding: utf-8 -*-
"""Public, engine-neutral models for document conversion."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class DocumentFormat(str, Enum):
    DOC = "doc"
    DOCX = "docx"
    ODT = "odt"
    PDF = "pdf"
    PPT = "ppt"
    PPTX = "pptx"
    RTF = "rtf"
    EPUB = "epub"
    EXCEL = "excel"
    ODS = "ods"
    ODP = "odp"
    CSV = "csv"


_BACKEND_NAMES = {
    DocumentFormat.EXCEL: "xlsx",
}


def backend_format_name(value: DocumentFormat) -> str:
    return _BACKEND_NAMES.get(value, value.value)


def document_format_from_backend(value: str) -> DocumentFormat:
    if value == "xlsx":
        return DocumentFormat.EXCEL
    return DocumentFormat(value)


@dataclass(frozen=True, slots=True)
class ConversionOptions:
    include_structure: bool = False
    include_assets: bool = False


@dataclass(frozen=True, slots=True)
class DocumentAsset:
    id: int
    media_type: str
    origin_part: str
    data: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class StructuredDocument:
    blocks: tuple[dict[str, Any], ...]
    notes: tuple[dict[str, Any], ...]
    assets: tuple[DocumentAsset, ...]


@dataclass(frozen=True, slots=True)
class ConvertedDocument:
    format: DocumentFormat
    markdown: str
    structure: StructuredDocument | None = None
    assets: tuple[DocumentAsset, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DocumentInput:
    content: bytes
    filename: str | None = None
    mime_type: str | None = None

    @classmethod
    def from_path(cls, path: str | Path) -> "DocumentInput":
        source = Path(path)
        return cls(content=source.read_bytes(), filename=source.name)
