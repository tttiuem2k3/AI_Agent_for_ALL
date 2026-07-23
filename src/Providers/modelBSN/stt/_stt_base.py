# -*- coding: utf-8 -*-
"""Provider-independent Speech-to-Text model contract."""
import inspect
from abc import abstractmethod
from pathlib import Path
from typing import Any, AsyncGenerator, Awaitable

from pydantic import BaseModel, Field

from _logging import logger
from Providers.credential import CredentialBase
from Runtime.message import DataBlock
from ._stt_model_card import STTModelCard
from ._stt_response import STTResponse


class STTModelBase:
    """Base class implemented by local or remote STT providers."""

    class Parameters(BaseModel):
        """Common transcription parameters."""

        language: str | None = Field(
            default=None,
            description="BCP-47 or provider-specific language hint.",
        )
        prompt: str | None = Field(
            default=None,
            description="Optional vocabulary or transcription hint.",
        )
        timestamps: bool = Field(
            default=True,
            description="Include timestamped segments when supported.",
        )

    realtime: bool = False

    def __init__(
        self,
        model: str,
        credential: CredentialBase | None = None,
        parameters: BaseModel | None = None,
        stream: bool = False,
    ) -> None:
        self.model = model
        self.credential = credential
        self.parameters = parameters or self.Parameters()
        self.stream = stream

    def __call__(
        self,
        audio: DataBlock,
        **kwargs: Any,
    ) -> Awaitable[STTResponse] | AsyncGenerator[STTResponse, None]:
        """Transcribe an audio block."""
        return self.transcribe(audio, **kwargs)

    @abstractmethod
    def transcribe(
        self,
        audio: DataBlock,
        **kwargs: Any,
    ) -> Awaitable[STTResponse] | AsyncGenerator[STTResponse, None]:
        """Transcribe audio and return normalized text/segments."""

    @classmethod
    def list_models(
        cls,
        custom_yaml_dir: str | None = None,
    ) -> list[STTModelCard]:
        """Load model cards from the concrete provider's ``_models`` folder."""
        yaml_dir = (
            Path(custom_yaml_dir)
            if custom_yaml_dir is not None
            else Path(inspect.getfile(cls)).parent / "_models"
        )
        if not yaml_dir.is_dir():
            return []

        cards: list[STTModelCard] = []
        for yaml_file in yaml_dir.glob("*.yaml"):
            try:
                cards.append(
                    STTModelCard.from_yaml(
                        str(yaml_file),
                        cls.Parameters,
                    ),
                )
            except Exception as error:
                logger.warning(
                    "Failed to load STT model card %s: %s",
                    yaml_file,
                    error,
                )
        return cards
