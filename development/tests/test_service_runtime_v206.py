# -*- coding: utf-8 -*-
"""AgentScope v2.0.6 additive service runtime contracts."""
import asyncio

import fakeredis.aioredis
import pytest

from Runtime.message import UserMsg, TextBlock
from Service.app.storage import RedisStorage


def test_list_messages_response_keeps_old_fields_and_adds_cursor_fields() -> None:
    from Service.app._router._schema import ListMessagesResponse

    response = ListMessagesResponse(messages=[], is_running=False)

    payload = response.model_dump()
    assert payload["messages"] == []
    assert payload["is_running"] is False
    assert payload["has_more"] is False
    assert payload["next_before"] is None


def test_health_router_exports_additive_root_health_endpoint() -> None:
    from Service.app._router import health_router

    routes = [route.path for route in health_router.routes]


    assert "/health" in routes


def test_redis_list_messages_uses_message_id_cursor_for_older_pages() -> None:
    async def _run() -> None:
        storage = RedisStorage()
        storage._client = fakeredis.aioredis.FakeRedis(decode_responses=True)
        storage.key_ttl = None

        for index in range(5):
            await storage.upsert_message(
                "u1",
                "s1",
                UserMsg(
                    id=f"m{index}",
                    name="user",
                    content=[TextBlock(text=str(index))],
                ),
            )

        latest, has_more = await storage.list_messages("u1", "s1", limit=2)
        assert [message.id for message in latest] == ["m3", "m4"]
        assert has_more is True

        older, has_more = await storage.list_messages(
            "u1",
            "s1",
            limit=2,
            before=latest[0].id,
        )
        assert [message.id for message in older] == ["m1", "m2"]
        assert has_more is True

        with pytest.warns(DeprecationWarning, match="offset parameter"):
            legacy, has_more = await storage.list_messages(
                "u1",
                "s1",
                offset=0,
                limit=2,
            )
        assert [message.id for message in legacy] == ["m0", "m1"]
        assert has_more is True


    asyncio.run(_run())
