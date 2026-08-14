# -*- coding: utf-8 -*-
"""HTTP coverage for the document conversion service API."""
import asyncio
from pathlib import Path
from types import SimpleNamespace

import httpx

from Service.app import create_app

FIXTURES = Path(__file__).parent / "fixtures" / "document_conversion"


def _app():
    return create_app(
        storage=SimpleNamespace(),
        message_bus=SimpleNamespace(),
        workspace_manager=SimpleNamespace(),
    )


def test_document_conversion_health_reports_native_backend() -> None:
    asyncio.run(_assert_health())


async def _assert_health() -> None:
    transport = httpx.ASGITransport(app=_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/document-conversion/health",
            headers={"X-User-ID": "web-ui-test"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["native_version"] == "0.1.9"


def test_document_conversion_api_converts_docx_to_markdown() -> None:
    asyncio.run(_assert_docx_conversion())


async def _assert_docx_conversion() -> None:
    source = FIXTURES / "docx" / "text.docx"
    transport = httpx.ASGITransport(app=_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/document-conversion/convert",
            headers={
                "X-User-ID": "web-ui-test",
                "X-File-Name": "text.docx",
                "Content-Type": "application/octet-stream",
            },
            content=source.read_bytes(),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["format"] == "docx"
    assert payload["markdown_chars"] == len(payload["markdown"])
    assert payload["markdown"].strip()
