# -*- coding: utf-8 -*-
"""Errors exposed by the generic document conversion capability."""
from __future__ import annotations


class DocumentConversionError(RuntimeError):
    """Stable, brand-neutral conversion error for callers."""

    def __init__(self, code: str, safe_message: str) -> None:
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message


class NativeBackendUnavailableError(DocumentConversionError):
    """Raised when the private native conversion artifact is not installed."""

    def __init__(self) -> None:
        super().__init__(
            "DOCUMENT_CONVERSION_BACKEND_UNAVAILABLE",
            "The native document conversion backend is not installed.",
        )
