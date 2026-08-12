# -*- coding: utf-8 -*-
"""ReMe-backed long-term memory middleware for ASOFT agents."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, AsyncGenerator, Callable, Literal, TYPE_CHECKING

from pydantic import BaseModel, Field

from ..._base import MiddlewareBase
from _logging import logger
from Runtime.message import AssistantMsg, HintBlock, Msg

if TYPE_CHECKING:
    from Runtime.agent import Agent
    from Capabilities.tool import ToolBase
    from Providers.modelBSN.embedding import EmbeddingModelBase
    from Providers.modelLLM.model import ChatModelBase

_SEARCH_JOB = "search"
_AUTO_MEMORY_JOB = "auto_memory"
_MEMORY_MSG_NAME = "memory"
_MEMORY_SECTION_HEADER = "## Relevant memories from past conversations"
_MEMORY_SECTION_INTRO = (
    "The following memories about the user may be relevant. "
    "Use them only if they are pertinent to the current request."
)
_TOOL_INSTRUCTIONS = (
    "## Long-term memory\n\n"
    "You have a `memory_search` tool available. Use it whenever the "
    "current conversation may depend on durable facts from past sessions. "
    "Recording memory is handled automatically; there is no add tool."
)


def _default_workspace_dir() -> Path:
    return Path.cwd() / "service" / "workspaces" / "reme"


class ReMeMiddleware(MiddlewareBase):
    """Optional ReMe in-process long-term memory middleware.

    The ``reme-ai`` package is imported lazily when the embedded app is first
    built, so importing ASOFT or ``Runtime.middleware`` does not require the
    optional ``memory-reme`` extra.
    """

    class Parameters(BaseModel):
        """User-tunable ReMe middleware parameters."""

        model_config = {"arbitrary_types_allowed": True}

        chat_model: Any | None = Field(default=None)
        embedding_model: Any | None = Field(default=None)
        mode: Literal["static_control", "agent_control", "both"] = "both"
        top_k: int = Field(default=5, gt=0)

    def __init__(
        self,
        *,
        workspace_dir: str | Path | None = None,
        config: str = "default",
        parameters: Parameters | None = None,
    ) -> None:
        self.workspace_dir = Path(workspace_dir) if workspace_dir else _default_workspace_dir()
        self._config = config
        self._parameters = parameters or self.Parameters()
        self._app: Any | None = None
        self._started = False
        self._retrieval_tasks: dict[str, asyncio.Task] = {}

    def _build_app(self) -> Any:
        try:
            from reme import ReMe
        except Exception as exc:  # pylint: disable=broad-exception-caught
            raise ImportError(
                "ReMeMiddleware requires optional extra `memory-reme`: "
                "install with `asoft-ai-services[memory-reme]`.",
            ) from exc

        kwargs: dict[str, Any] = {
            "workspace_dir": str(self.workspace_dir),
            "config": self._config,
        }
        if self._parameters.chat_model is not None:
            kwargs["chat_model"] = self._parameters.chat_model
        if self._parameters.embedding_model is not None:
            kwargs["embedding_model"] = self._parameters.embedding_model
        return ReMe(**kwargs)

    async def _ensure_started(self) -> None:
        if self._app is None:
            self._app = self._build_app()
        if self._started:
            return
        start = getattr(self._app, "start", None)
        if start is not None:
            result = start()
            if hasattr(result, "__await__"):
                await result
        self._started = True

    async def close(self) -> None:
        if self._app is None:
            return
        stop = getattr(self._app, "stop", None) or getattr(self._app, "close", None)
        if stop is not None:
            result = stop()
            if hasattr(result, "__await__"):
                await result
        self._started = False

    @staticmethod
    def _session_id_of(agent: "Agent") -> str | None:
        return getattr(agent.state, "session_id", None)

    async def on_reply(
        self,
        agent: "Agent",
        input_kwargs: dict,
        next_handler: Callable[..., AsyncGenerator],
    ) -> AsyncGenerator:
        session_id = self._session_id_of(agent)
        query_text = _extract_query_text(input_kwargs.get("inputs"))
        pre_ids = {m.id for m in agent.state.context if isinstance(m, Msg)}

        if (
            session_id
            and query_text
            and self._parameters.mode in ("static_control", "both")
        ):
            self._retrieval_tasks[session_id] = asyncio.create_task(
                self._search(query_text, limit=self._parameters.top_k),
            )

        try:
            async for item in next_handler(**input_kwargs):
                yield item
        finally:
            task = self._retrieval_tasks.pop(session_id, None) if session_id else None
            if task is not None and not task.done():
                task.cancel()
            if task is not None:
                try:
                    await task
                except (asyncio.CancelledError, Exception):  # noqa: BLE001
                    pass
            increment = [
                m
                for m in agent.state.context
                if isinstance(m, Msg)
                and m.id not in pre_ids
                and getattr(m, "name", None) != _MEMORY_MSG_NAME
            ]
            if session_id and query_text and any(m.role == "assistant" and m.get_text_content() for m in increment):
                await self._write_back(increment, session_id)

    async def on_reasoning(
        self,
        agent: "Agent",
        input_kwargs: dict,
        next_handler: Callable[..., AsyncGenerator],
    ) -> AsyncGenerator:
        session_id = self._session_id_of(agent)
        task = self._retrieval_tasks.get(session_id) if session_id else None
        if task is not None and task.done():
            self._retrieval_tasks.pop(session_id, None)
            try:
                memories = task.result()
            except (asyncio.CancelledError, Exception) as exc:  # noqa: BLE001
                logger.warning("ReMe search failed: %s", exc)
                memories = []
            if memories:
                agent.state.context.append(self._build_memory_message(memories))

        async for event in next_handler(**input_kwargs):
            yield event

    async def on_system_prompt(self, agent: "Agent", current_prompt: str) -> str:
        if self._parameters.mode == "static_control":
            return current_prompt
        return f"{current_prompt}\n\n{_TOOL_INSTRUCTIONS}"

    async def list_tools(self) -> list["ToolBase"]:
        if self._parameters.mode == "static_control":
            return []
        from ._tools import _build_memory_tools

        return _build_memory_tools(self)

    async def _run_job(self, name: str, **kwargs: Any) -> Any:
        await self._ensure_started()
        runner = getattr(self._app, "run_job", None)
        if runner is None:
            runner = getattr(self._app, "run", None)
        if runner is None:
            raise RuntimeError("ReMe app does not expose run_job/run.")
        result = runner(name, **kwargs)
        if hasattr(result, "__await__"):
            return await result
        return result

    async def _search(self, query: str, limit: int | None = None) -> list[str]:
        raw = await self._run_job(
            _SEARCH_JOB,
            query=query,
            top_k=limit or self._parameters.top_k,
        )
        return _extract_memory_texts(raw)

    async def _write_back(self, messages: list[Msg], session_id: str) -> None:
        if not messages:
            return
        try:
            await self._run_job(
                _AUTO_MEMORY_JOB,
                messages=[m.model_dump(mode="json") for m in messages],
                session_id=session_id,
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("ReMe auto-memory write-back failed: %s", exc)

    @staticmethod
    def _build_memory_message(memories: list[str]) -> Msg:
        joined = "\n".join(f"- {memory}" for memory in memories)
        return AssistantMsg(
            name=_MEMORY_MSG_NAME,
            content=[
                HintBlock(
                    source='{"label": "System", "sublabel": "Memory"}',
                    hint=(
                        f"{_MEMORY_SECTION_HEADER}\n\n"
                        f"{_MEMORY_SECTION_INTRO}\n\n{joined}"
                    ),
                ),
            ],
        )


def _extract_query_text(inputs: Any) -> str | None:
    from Runtime.event import ExternalExecutionResultEvent, UserConfirmResultEvent, UserInterruptEvent

    if inputs is None or isinstance(
        inputs,
        (ExternalExecutionResultEvent, UserConfirmResultEvent, UserInterruptEvent),
    ):
        return None
    messages = inputs if isinstance(inputs, list) else [inputs]
    texts = [
        message.get_text_content()
        for message in messages
        if isinstance(message, Msg)
        and message.role == "user"
        and message.get_text_content()
    ]
    return "\n".join(texts) if texts else None


def _extract_memory_texts(raw: Any) -> list[str]:
    if raw is None:
        return []
    results: Any = raw
    if isinstance(raw, dict):
        if isinstance(raw.get("metadata"), dict) and "results" in raw["metadata"]:
            results = raw["metadata"]["results"]
        else:
            results = raw.get("results", raw)
    if not isinstance(results, list):
        return []
    output: list[str] = []
    for item in results:
        if isinstance(item, str):
            output.append(item)
        elif isinstance(item, dict):
            text = item.get("text") or item.get("memory") or item.get("content")
            if text:
                output.append(str(text))
    return output
