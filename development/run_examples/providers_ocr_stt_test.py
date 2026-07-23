# -*- coding: utf-8 -*-
"""Tests for the provider-independent OCR and STT contracts."""
import asyncio
from pathlib import Path
from typing import Any

from Providers import (
    OCRModelBase,
    OCRModelCard,
    OCRResponse,
    STTModelBase,
    STTModelCard,
    STTResponse,
    STTSegment,
)
from Runtime.message import Base64Source, DataBlock


class DummyOCRModel(OCRModelBase):
    """Minimal OCR provider used to verify the public contract."""

    async def recognize(
        self,
        document: DataBlock,
        **kwargs: Any,
    ) -> OCRResponse:
        return OCRResponse(text=f"recognized:{document.source.media_type}")


class DummySTTModel(STTModelBase):
    """Minimal STT provider used to verify the public contract."""

    async def transcribe(
        self,
        audio: DataBlock,
        **kwargs: Any,
    ) -> STTResponse:
        return STTResponse(
            text="xin chào",
            segments=[STTSegment(text="xin chào", start=0.0, end=1.0)],
            language="vi",
        )


def test_ocr_contract_accepts_data_block() -> None:
    model = DummyOCRModel(model="dummy-ocr")
    document = DataBlock(
        source=Base64Source(media_type="image/png", data="AA=="),
    )

    response = asyncio.run(model(document))

    assert response.type == "ocr"
    assert response.text == "recognized:image/png"


def test_stt_contract_accepts_data_block() -> None:
    model = DummySTTModel(model="dummy-stt")
    audio = DataBlock(
        source=Base64Source(media_type="audio/wav", data="AA=="),
    )

    response = asyncio.run(model(audio))

    assert response.type == "stt"
    assert response.language == "vi"
    assert response.segments[0].start == 0.0


def test_ocr_model_card_from_yaml(tmp_path: Path) -> None:
    yaml_path = tmp_path / "ocr.yaml"
    yaml_path.write_text(
        "\n".join(
            [
                "name: paddleocr-vi",
                "label: PaddleOCR Vietnamese",
                "languages: [vi, en]",
                "input_types: [image/png, image/jpeg, app/pdf]",
            ],
        ),
        encoding="utf-8",
    )

    card = OCRModelCard.from_yaml(
        str(yaml_path),
        DummyOCRModel.Parameters,
    )

    assert card.type == "ocr_model"
    assert card.languages == ["vi", "en"]
    assert "app/pdf" in card.input_types


def test_stt_model_card_from_yaml(tmp_path: Path) -> None:
    yaml_path = tmp_path / "stt.yaml"
    yaml_path.write_text(
        "\n".join(
            [
                "name: faster-whisper-large-v3",
                "label: Faster Whisper Large v3",
                "languages: [vi, en]",
                "realtime: false",
                "input_types: [audio/wav, audio/mpeg]",
            ],
        ),
        encoding="utf-8",
    )

    card = STTModelCard.from_yaml(
        str(yaml_path),
        DummySTTModel.Parameters,
    )

    assert card.type == "stt_model"
    assert card.languages == ["vi", "en"]
    assert card.realtime is False
