# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from Capabilities.document_conversion import (
    ConversionOptions,
    DocumentConversionService,
    DocumentFormat,
)


class FakeBackend:
    def format_from_bytes(self, data: bytes) -> str | None:
        return "docx" if data.startswith(b"DOC") else None

    def format_from_extension(self, extension: str) -> str | None:
        return "xlsx" if extension.lower() in {".xls", ".xlsx"} else None

    def to_markdown_bytes(self, data: bytes, format_name: str | None) -> str:
        return f"# {format_name}\n\nConverted\n"

    def to_document(self, data: bytes, format_name: str | None):
        return SimpleNamespace(blocks=[], notes=[], assets=[])


def test_document_conversion_detects_content_without_native_dependency() -> None:
    service = DocumentConversionService(FakeBackend())
    result = asyncio.run(service.convert(b"DOC-content", filename="sample.bin"))

    assert result.format is DocumentFormat.DOCX
    assert result.markdown == "# docx\n\nConverted\n"
    assert result.structure is None
    assert result.assets == ()


def test_document_conversion_uses_extension_fallback() -> None:
    service = DocumentConversionService(FakeBackend())
    result = asyncio.run(service.convert(b"sheet", filename="report.xls"))

    assert result.format is DocumentFormat.EXCEL
    assert result.markdown.startswith("# xlsx")


def test_document_conversion_can_request_structure() -> None:
    service = DocumentConversionService(FakeBackend())
    result = asyncio.run(
        service.convert(
            b"DOC-content",
            options=ConversionOptions(include_structure=True),
        )
    )

    assert result.structure is not None
    assert result.structure.blocks == ()


def test_rag_document_conversion_parser_adapts_markdown_to_section() -> None:
    from Capabilities.rag import DocumentConversionParser

    parser = DocumentConversionParser(DocumentConversionService(FakeBackend()))
    sections = asyncio.run(parser.parse(b"DOC-content", "guide.docx"))

    assert len(sections) == 1
    assert sections[0].content.text.startswith("# docx")
    assert sections[0].source == "guide.docx"
    assert sections[0].metadata["format"] == "docx"


def test_native_unsupported_ocr_error_maps_to_stable_code() -> None:
    from Capabilities.document_conversion._backend import _map_native_error

    class UnsupportedError(Exception):
        pass

    module = SimpleNamespace(UnsupportedError=UnsupportedError)
    error = _map_native_error(module, UnsupportedError("image-only PDF needs OCR"))

    assert error.code == "DOCUMENT_OCR_REQUIRED"
