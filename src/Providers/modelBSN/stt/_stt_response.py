# -*- coding: utf-8 -*-
"""Response types shared by Speech-to-Text providers."""
from dataclasses import dataclass, field
from typing import Literal

from Common._utils._common import _get_timestamp
from Common._utils._mixin import DictMixin
from Common.types import JSONSerializableObject


@dataclass
class STTSegment(DictMixin):
    """A timestamped transcription segment."""

    text: str
    start: float
    end: float
    confidence: float | None = field(default_factory=lambda: None)
    speaker: str | None = field(default_factory=lambda: None)


@dataclass
class STTUsage(DictMixin):
    """Resource usage reported by an STT invocation."""

    audio_seconds: float
    time: float
    type: Literal["stt"] = field(default_factory=lambda: "stt")


@dataclass
class STTResponse(DictMixin):
    """Normalized transcription returned by every STT provider."""

    text: str
    segments: list[STTSegment] = field(default_factory=list)
    id: str = field(default_factory=lambda: _get_timestamp(True))
    created_at: str = field(default_factory=_get_timestamp)
    type: Literal["stt"] = field(default_factory=lambda: "stt")
    language: str | None = field(default_factory=lambda: None)
    usage: STTUsage | None = field(default_factory=lambda: None)
    metadata: dict[str, JSONSerializableObject] | None = field(
        default_factory=lambda: None,
    )
    is_last: bool = field(default_factory=lambda: True)
