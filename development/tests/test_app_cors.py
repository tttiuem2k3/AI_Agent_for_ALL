# -*- coding: utf-8 -*-
"""CORS behavior for the FastAPI app factory."""
import asyncio
from types import SimpleNamespace

import httpx

from Service.app import create_app


def test_allows_web_ui_preflight_from_private_lan() -> None:
    asyncio.run(_assert_web_ui_preflight_is_allowed())


async def _assert_web_ui_preflight_is_allowed() -> None:
    app = create_app(
        storage=SimpleNamespace(),
        message_bus=SimpleNamespace(),
        workspace_manager=SimpleNamespace(),
    )
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.options(
            "/agent/",
            headers={
                "Origin": "http://192.168.0.134:5173",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "x-user-id",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "http://192.168.0.134:5173"
    )
    assert "x-user-id" in response.headers[
        "access-control-allow-headers"
    ].lower()
