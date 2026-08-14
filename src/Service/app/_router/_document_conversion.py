# -*- coding: utf-8 -*-
"""HTTP API for the generic document-to-Markdown capability."""
from __future__ import annotations

import importlib
from importlib.metadata import PackageNotFoundError, version
import platform
from time import perf_counter
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from Capabilities.document_conversion import (
    DocumentConversionError,
    DocumentConversionService,
    NativeBackendUnavailableError,
)
from ..deps import get_current_user_id

MAX_DOCUMENT_BYTES = 50 * 1024 * 1024
NATIVE_DISTRIBUTION = "asoft-document-conversion-native"

document_conversion_router = APIRouter(
    prefix="/document-conversion",
    tags=["document-conversion"],
)
class DocumentConversionHealthResponse(BaseModel):
    """Document conversion runtime availability."""

    ok: bool
    native_version: str | None = None
    python: str


class DocumentConversionResponse(BaseModel):
    """Markdown conversion result returned to API clients."""

    ok: bool = True
    filename: str
    format: str
    markdown: str
    warnings: list[str] = Field(default_factory=list)
    elapsed_ms: float
    input_bytes: int
    markdown_chars: int
    native_version: str | None = None


def _native_version() -> str | None:
    try:
        return version(NATIVE_DISTRIBUTION)
    except PackageNotFoundError:
        return None
async def _read_limited_body(request: Request) -> bytes:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            declared_size = int(content_length)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Content-Length header.",
            ) from exc
        if declared_size > MAX_DOCUMENT_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Document exceeds the 50 MB upload limit.",
            )

    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > MAX_DOCUMENT_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Document exceeds the 50 MB upload limit.",
            )
        chunks.append(chunk)
    if total == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document body is empty.",
        )
    return b"".join(chunks)
@document_conversion_router.get(
    "/health",
    response_model=DocumentConversionHealthResponse,
    summary="Document conversion runtime health",
)
async def document_conversion_health(
    _caller_id: str = Depends(get_current_user_id),
) -> DocumentConversionHealthResponse:
    """Verify that the compiled native document conversion backend is importable."""
    native_version = _native_version()
    try:
        importlib.import_module("asoft_document_conversion_native")
    except ImportError:
        return DocumentConversionHealthResponse(
            ok=False,
            native_version=native_version,
            python=platform.python_version(),
        )
    return DocumentConversionHealthResponse(
        ok=True,
        native_version=native_version,
        python=platform.python_version(),
    )


@document_conversion_router.post(
    "/convert",
    response_model=DocumentConversionResponse,
    summary="Convert a document to Markdown",
)
async def convert_document(
    request: Request,
    x_file_name: str = Header(alias="X-File-Name"),
    _caller_id: str = Depends(get_current_user_id),
) -> DocumentConversionResponse:
    """Convert one binary document request body into Markdown."""
    filename = unquote(x_file_name).strip()
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-File-Name header is required.",
        )

    content = await _read_limited_body(request)
    started = perf_counter()
    try:
        converted = await DocumentConversionService().convert(
            content,
            filename=filename,
        )
    except NativeBackendUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=exc.safe_message,
        ) from exc
    except DocumentConversionError as exc:
        error_status = (
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            if exc.code == "DOCUMENT_RESOURCE_LIMIT"
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=error_status, detail=exc.safe_message) from exc
    elapsed_ms = round((perf_counter() - started) * 1000, 2)
    markdown = converted.markdown
    return DocumentConversionResponse(
        filename=filename,
        format=converted.format.value,
        markdown=markdown,
        warnings=list(converted.warnings),
        elapsed_ms=elapsed_ms,
        input_bytes=len(content),
        markdown_chars=len(markdown),
        native_version=_native_version(),
    )
