# -*- coding: utf-8 -*-
"""Public document conversion service."""
from __future__ import annotations

import asyncio
from pathlib import Path

from ._base import DocumentConversionBackend
from ._errors import DocumentConversionError
from ._models import (
    ConversionOptions,
    ConvertedDocument,
    DocumentFormat,
    StructuredDocument,
    backend_format_name,
    document_format_from_backend,
)
from ._backend import NativeDocumentConversionBackend
from ._structure import convert_native_document


class DocumentConversionService:
    """Convert supported office/document formats into normalized Markdown."""

    def __init__(self, backend: DocumentConversionBackend | None = None) -> None:
        self._backend = backend or NativeDocumentConversionBackend()

    async def convert_file(
        self,
        path: str | Path,
        *,
        options: ConversionOptions | None = None,
    ) -> ConvertedDocument:
        source = Path(path)
        content = await asyncio.to_thread(source.read_bytes)
        return await self.convert(content, filename=source.name, options=options)

    async def convert(
        self,
        content: bytes,
        *,
        filename: str | None = None,
        mime_type: str | None = None,
        format: DocumentFormat | None = None,
        options: ConversionOptions | None = None,
    ) -> ConvertedDocument:
        del mime_type  # Reserved for future policy/routing without coupling the engine.
        selected = options or ConversionOptions()
        return await asyncio.to_thread(
            self._convert_sync,
            content,
            filename,
            format,
            selected,
        )

    def _convert_sync(
        self,
        content: bytes,
        filename: str | None,
        format: DocumentFormat | None,
        options: ConversionOptions,
    ) -> ConvertedDocument:
        backend_name = backend_format_name(format) if format is not None else None
        if backend_name is None:
            backend_name = self._backend.format_from_bytes(content)
        if backend_name is None and filename:
            suffix = Path(filename).suffix
            if suffix:
                backend_name = self._backend.format_from_extension(suffix)
        if backend_name is None:
            raise DocumentConversionError(
                "DOCUMENT_FORMAT_UNSUPPORTED",
                "The document format could not be detected.",
            )

        resolved_format = document_format_from_backend(backend_name)
        markdown = self._backend.to_markdown_bytes(content, backend_name)
        warnings: list[str] = []
        structure: StructuredDocument | None = None
        assets = ()

        wants_native_document = options.include_structure or options.include_assets
        if wants_native_document:
            if resolved_format == DocumentFormat.PDF:
                warnings.append("STRUCTURE_UNAVAILABLE_FOR_PDF")
            else:
                native_document = self._backend.to_document(content, backend_name)
                parsed = convert_native_document(native_document)
                if options.include_assets:
                    assets = parsed.assets
                if options.include_structure:
                    structure = parsed if options.include_assets else StructuredDocument(
                        blocks=parsed.blocks,
                        notes=parsed.notes,
                        assets=(),
                    )

        return ConvertedDocument(
            format=resolved_format,
            markdown=markdown,
            structure=structure,
            assets=assets,
            warnings=tuple(warnings),
        )
