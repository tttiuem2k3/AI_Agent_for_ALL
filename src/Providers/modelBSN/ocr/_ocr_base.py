# -*- coding: utf-8 -*-
"""Provider-independent OCR model contract."""
import inspect
from abc import abstractmethod
from pathlib import Path
from typing import Any, AsyncGenerator, Awaitable

from pydantic import BaseModel, Field

from _logging import logger
from Providers.credential import CredentialBase
from Runtime.message import DataBlock
from ._ocr_model_card import OCRModelCard
from ._ocr_response import OCRResponse


class OCRModelBase:
    """Base class implemented by local or remote OCR providers."""

    class Parameters(BaseModel):
        """Common OCR parameters."""

        language: str | None = Field(
            default=None,
            description="Preferred recognition language, if known.",
        )
        detect_orientation: bool = Field(
            default=True,
            description="Detect and correct page/text orientation.",
        )

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
        document: DataBlock,
        **kwargs: Any,
    ) -> Awaitable[OCRResponse] | AsyncGenerator[OCRResponse, None]:
        """Recognize text in an image or document."""
        return self.recognize(document, **kwargs)

    @abstractmethod
    def recognize(
        self,
        document: DataBlock,
        **kwargs: Any,
    ) -> Awaitable[OCRResponse] | AsyncGenerator[OCRResponse, None]:
        """Recognize text and return normalized text/layout output."""

    @classmethod
    def list_models(
        cls,
        custom_yaml_dir: str | None = None,
    ) -> list[OCRModelCard]:
        """Load model cards from the concrete provider's ``_models`` folder."""
        yaml_dir = (
            Path(custom_yaml_dir)
            if custom_yaml_dir is not None
            else Path(inspect.getfile(cls)).parent / "_models"
        )
        if not yaml_dir.is_dir():
            return []

        cards: list[OCRModelCard] = []
        for yaml_file in yaml_dir.glob("*.yaml"):
            try:
                cards.append(
                    OCRModelCard.from_yaml(
                        str(yaml_file),
                        cls.Parameters,
                    ),
                )
            except Exception as error:
                logger.warning(
                    "Failed to load OCR model card %s: %s",
                    yaml_file,
                    error,
                )
        return cards
