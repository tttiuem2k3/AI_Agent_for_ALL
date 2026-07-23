# -*- coding: utf-8 -*-
"""Optical Character Recognition provider abstractions."""

from ._ocr_base import OCRModelBase
from ._ocr_model_card import OCRModelCard
from ._ocr_response import OCRPage, OCRResponse, OCRTextBlock, OCRUsage

__all__ = [
    "OCRModelBase",
    "OCRModelCard",
    "OCRPage",
    "OCRResponse",
    "OCRTextBlock",
    "OCRUsage",
]
