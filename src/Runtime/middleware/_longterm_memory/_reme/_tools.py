# -*- coding: utf-8 -*-
"""Agent-control tool exposed by the ReMe middleware."""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from Capabilities.permission import PermissionBehavior, PermissionDecision
from Capabilities.tool import ToolBase, ToolChunk
from Runtime.message import TextBlock, ToolResultState

if TYPE_CHECKING:
    from ._middleware import ReMeMiddleware


class _ReMeMemoryToolBase(ToolBase):
    is_external_tool = False
    is_state_injected = False
    is_mcp = False
    mcp_name = None

    def __init__(self, mw: "ReMeMiddleware") -> None:
        self._mw = mw

    async def check_permissions(self, *_args: Any, **_kwargs: Any) -> PermissionDecision:
        return PermissionDecision(
            behavior=PermissionBehavior.ALLOW,
            message="auto-allowed: ReMe long-term memory tool",
        )


class _MemorySearchTool(_ReMeMemoryToolBase):
    name = "memory_search"
    description = "Retrieve memories from past conversations relevant to a query."
    is_concurrency_safe = True
    is_read_only = True

    def __init__(self, mw: "ReMeMiddleware") -> None:
        super().__init__(mw)
        self.input_schema = {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of memories to retrieve.",
                    "default": mw._parameters.top_k,
                },
            },
            "required": ["query"],
        }

    async def call(self, query: str, limit: int | None = None) -> ToolChunk:
        if not query:
            return _text_chunk("(no query supplied - nothing to search)")
        try:
            memories = await self._mw._search(query, limit=limit)
        except Exception as exc:  # noqa: BLE001
            return _error_chunk(f"Error retrieving memory: {exc}")
        if not memories:
            return _text_chunk("(no relevant memories found)")
        return _text_chunk("\n".join(f"- {memory}" for memory in memories))


def _build_memory_tools(mw: "ReMeMiddleware") -> list[ToolBase]:
    return [_MemorySearchTool(mw)]


def _text_chunk(message: str) -> ToolChunk:
    return ToolChunk(content=[TextBlock(text=message)])


def _error_chunk(message: str) -> ToolChunk:
    return ToolChunk(
        content=[TextBlock(text=message)],
        state=ToolResultState.ERROR,
    )
