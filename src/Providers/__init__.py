# -*- coding: utf-8 -*-
"""Public provider abstractions for ASOFT AI Services."""

from .modelBSN.ocr import (
    OCRModelBase,
    OCRModelCard,
    OCRPage,
    OCRResponse,
    OCRTextBlock,
    OCRUsage,
)
from .modelBSN.stt import (
    STTModelBase,
    STTModelCard,
    STTResponse,
    STTSegment,
    STTUsage,
)

__all__ = [
    "OCRModelBase",
    "OCRModelCard",
    "OCRPage",
    "OCRResponse",
    "OCRTextBlock",
    "OCRUsage",
    "STTModelBase",
    "STTModelCard",
    "STTResponse",
    "STTSegment",
    "STTUsage",
]
