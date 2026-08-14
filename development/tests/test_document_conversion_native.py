# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import importlib.metadata
from pathlib import Path

import pytest

from Capabilities.document_conversion import (
    ConversionOptions,
    DocumentConversionError,
    DocumentConversionService,
    DocumentFormat,
)

FIXTURES = Path(__file__).parent / "fixtures" / "document_conversion"

CASES = [
    ("csv/sheet.csv", DocumentFormat.CSV),
    ("doc/text.doc", DocumentFormat.DOC),
    ("docx/text.docx", DocumentFormat.DOCX),
    ("epub/book.epub", DocumentFormat.EPUB),
    ("odt/text.odt", DocumentFormat.ODT),
    ("pdf/text.pdf", DocumentFormat.PDF),
    ("ppt/pres.ppt", DocumentFormat.PPT),
    ("pptx/pres.pptx", DocumentFormat.PPTX),
]

CASES += [
    ("rtf/text.rtf", DocumentFormat.RTF),
    ("xls/sheet.xls", DocumentFormat.EXCEL),
    ("xlsx/sheet.xlsx", DocumentFormat.EXCEL),
    ("ods/sheet.ods", DocumentFormat.ODS),
    ("odp/pres.odp", DocumentFormat.ODP),
]


def test_native_distribution_is_installed() -> None:
    assert importlib.metadata.version("asoft-document-conversion-native") == "0.1.9"


@pytest.mark.parametrize(("relative_path", "expected_format"), CASES)
def test_native_converts_real_fixture(
    relative_path: str,
    expected_format: DocumentFormat,
) -> None:
    result = asyncio.run(
        DocumentConversionService().convert_file(FIXTURES / relative_path)
    )

    assert result.format is expected_format
    assert result.markdown.strip()


def test_native_exposes_structure_for_docx() -> None:
    result = asyncio.run(
        DocumentConversionService().convert_file(
            FIXTURES / "docx" / "text.docx",
            options=ConversionOptions(include_structure=True),
        )
    )

    assert result.structure is not None
    assert result.structure.blocks


def test_pdf_structure_request_returns_stable_warning() -> None:
    result = asyncio.run(
        DocumentConversionService().convert_file(
            FIXTURES / "pdf" / "text.pdf",
            options=ConversionOptions(include_structure=True),
        )
    )

    assert result.structure is None
    assert "STRUCTURE_UNAVAILABLE_FOR_PDF" in result.warnings


def test_encrypted_document_maps_to_stable_error() -> None:
    with pytest.raises(DocumentConversionError) as caught:
        asyncio.run(
            DocumentConversionService().convert_file(
                FIXTURES / "malformed" / "encrypted--errors.odt"
            )
        )

    assert caught.value.code == "DOCUMENT_ENCRYPTED"


def test_empty_docx_maps_to_stable_error() -> None:
    with pytest.raises(DocumentConversionError) as caught:
        asyncio.run(
            DocumentConversionService().convert_file(
                FIXTURES / "malformed" / "empty--errors.docx"
            )
        )

    assert caught.value.code in {"DOCUMENT_MALFORMED", "DOCUMENT_CONVERSION_FAILED"}
