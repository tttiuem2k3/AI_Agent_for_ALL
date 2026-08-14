# -*- coding: utf-8 -*-
"""Knowledge Factory adapter for source document conversion."""
from __future__ import annotations

from Capabilities.document_conversion import (
    ConversionOptions,
    ConvertedDocument,
    DocumentConversionService,
    DocumentFormat,
)


class KnowledgeFactorySourceConverter:
    """Apply Knowledge Factory-specific conversion choices without coupling the capability."""

    def __init__(self, converter: DocumentConversionService | None = None) -> None:
        self.converter = converter or DocumentConversionService()

    async def convert_source(
        self,
        content: bytes,
        *,
        filename: str | None = None,
        mime_type: str | None = None,
        format: DocumentFormat | None = None,
        include_structure: bool = True,
        include_assets: bool = False,
    ) -> ConvertedDocument:
        return await self.converter.convert(
            content,
            filename=filename,
            mime_type=mime_type,
            format=format,
            options=ConversionOptions(
                include_structure=include_structure,
                include_assets=include_assets,
            ),
        )
