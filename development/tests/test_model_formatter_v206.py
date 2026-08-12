# -*- coding: utf-8 -*-
"""AgentScope v2.0.6 model formatter regression tests."""
import asyncio

from Providers.modelLLM.formatter import (
    AnthropicChatFormatter,
    GeminiChatFormatter,
    OllamaChatFormatter,
)
from Runtime.message import (
    AssistantMsg,
    TextBlock,
    ThinkingBlock,
    ToolCallBlock,
    ToolResultBlock,
)


def test_anthropic_formatter_repairs_truncated_tool_input() -> None:
    async def _run() -> None:
        formatted = await AnthropicChatFormatter().format(
                [AssistantMsg("assistant", [ToolCallBlock(id="call-1", name="tool", input='{"city": "Tok')])],
            )
        assert formatted[0]["content"][0]["input"] == {"city": "Tok"}

    asyncio.run(_run())


def test_anthropic_formatter_drops_empty_text_outputs() -> None:
    async def _run() -> None:
        formatted = await AnthropicChatFormatter().format(
            [AssistantMsg("assistant", [TextBlock(text="")])],
        )
        assert formatted == []

    asyncio.run(_run())


def test_anthropic_formatter_preserves_redacted_thinking() -> None:
    async def _run() -> None:
        formatted = await AnthropicChatFormatter().format(
            [
                AssistantMsg(
                    "assistant",
                    [
                        ThinkingBlock(
                            thinking="",
                            redacted_thinking_data="encrypted-payload",
                        ),
                    ],
                ),
            ],
        )
        assert formatted[0]["content"][0] == {
            "type": "redacted_thinking",
            "data": "encrypted-payload",
        }

    asyncio.run(_run())


def test_gemini_formatter_skips_empty_thinking() -> None:
    async def _run() -> None:
        formatted = await GeminiChatFormatter().format(
            [AssistantMsg("assistant", [ThinkingBlock(thinking="")])],
        )
        assert formatted == []

    asyncio.run(_run())


def test_ollama_formatter_repairs_tool_input_and_sets_tool_name() -> None:
    async def _run() -> None:
        formatted = await OllamaChatFormatter().format(
            [AssistantMsg("assistant", [
                ToolCallBlock(id="call-1", name="lookup", input='{"q": "abc'),
                ToolResultBlock(id="call-1", name="lookup", output="ok"),
            ])],
        )
        assert formatted[0]["tool_calls"][0]["function"]["arguments"] == {"q": "abc"}
        assert formatted[1]["tool_name"] == "lookup"

    asyncio.run(_run())
