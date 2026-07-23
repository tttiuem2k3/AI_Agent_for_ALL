# -*- coding: utf-8 -*-
"""Response types shared by OCR providers."""
from dataclasses import dataclass, field
from typing import Literal

from Common._utils._common import _get_timestamp
from Common._utils._mixin import DictMixin
from Common.types import JSONSerializableObject


@dataclass
class OCRTextBlock(DictMixin):
    """A recognized text region and its optional layout information."""

    text: str
    confidence: float | None = field(default_factory=lambda: None)
    bounding_box: list[list[float]] | None = field(
        default_factory=lambda: None,
    )
    page: int | None = field(default_factory=lambda: None)


@dataclass
class OCRPage(DictMixin):
    """OCR output for one page or image."""

    page: int
    text: str
    blocks: list[OCRTextBlock] = field(default_factory=list)
    width: int | None = field(default_factory=lambda: None)
    height: int | None = field(default_factory=lambda: None)


@dataclass
class OCRUsage(DictMixin):
    """Resource usage reported by an OCR invocation."""

    pages: int
    time: float
    type: Literal["ocr"] = field(default_factory=lambda: "ocr")


@dataclass
class OCRResponse(DictMixin):
    """Normalized response returned by every OCR provider."""

    text: str
    pages: list[OCRPage] = field(default_factory=list)
    id: str = field(default_factory=lambda: _get_timestamp(True))
    created_at: str = field(default_factory=_get_timestamp)
    type: Literal["ocr"] = field(default_factory=lambda: "ocr")
    language: str | None = field(default_factory=lambda: None)
    usage: OCRUsage | None = field(default_factory=lambda: None)
    metadata: dict[str, JSONSerializableObject] | None = field(
        default_factory=lambda: None,
    )
    is_last: bool = field(default_factory=lambda: True)
