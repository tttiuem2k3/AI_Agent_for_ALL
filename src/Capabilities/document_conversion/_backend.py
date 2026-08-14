# -*- coding: utf-8 -*-
"""Adapter around the private ASOFT native document conversion artifact."""
from __future__ import annotations

import importlib
from typing import Any

from ._errors import DocumentConversionError, NativeBackendUnavailableError


class NativeDocumentConversionBackend:
    """Lazy-load the compiled native backend so importing Capabilities stays cheap."""

    def __init__(self) -> None:
        self._module: Any | None = None

    def _load(self) -> Any:
        if self._module is not None:
            return self._module
        try:
            self._module = importlib.import_module("asoft_document_conversion_native")
        except ImportError as exc:
            raise NativeBackendUnavailableError() from exc
        return self._module

    def format_from_bytes(self, data: bytes) -> str | None:
        return self._call("format_from_bytes", data)

    def format_from_extension(self, extension: str) -> str | None:
        return self._call("format_from_extension", extension)

    def to_markdown_bytes(self, data: bytes, format_name: str | None) -> str:
        return self._call("to_markdown_bytes", data, format_name)

    def to_document(self, data: bytes, format_name: str | None) -> Any:
        return self._call("to_document", data, format_name)

    def _call(self, function_name: str, *args: Any) -> Any:
        module = self._load()
        try:
            return getattr(module, function_name)(*args)
        except Exception as exc:
            raise _map_native_error(module, exc) from exc


def _map_native_error(module: Any, exc: Exception) -> DocumentConversionError:
    mappings = (
        ("UnsupportedError", "DOCUMENT_FORMAT_UNSUPPORTED"),
        ("MalformedError", "DOCUMENT_MALFORMED"),
        ("EncryptedError", "DOCUMENT_ENCRYPTED"),
        ("ResourceLimitError", "DOCUMENT_RESOURCE_LIMIT"),
        ("MissingPartError", "DOCUMENT_MISSING_PART"),
    )
    for name, code in mappings:
        error_type = getattr(module, name, None)
        if error_type is not None and isinstance(exc, error_type):
            message = str(exc)
            if name == "UnsupportedError" and "OCR" in message.upper():
                return DocumentConversionError("DOCUMENT_OCR_REQUIRED", message)
            return DocumentConversionError(code, message)
    if isinstance(exc, OSError):
        return DocumentConversionError("DOCUMENT_IO_ERROR", str(exc))
    return DocumentConversionError("DOCUMENT_CONVERSION_FAILED", str(exc))
