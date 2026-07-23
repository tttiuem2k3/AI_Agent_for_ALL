# -*- coding: utf-8 -*-
"""Speech-to-Text provider abstractions."""

from ._stt_base import STTModelBase
from ._stt_model_card import STTModelCard
from ._stt_response import STTResponse, STTSegment, STTUsage

__all__ = [
    "STTModelBase",
    "STTModelCard",
    "STTResponse",
    "STTSegment",
    "STTUsage",
]
