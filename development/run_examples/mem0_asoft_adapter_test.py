# -*- coding: utf-8 -*-
# pylint: disable=wrong-import-order
"""Unit tests for the ASOFT AI Services ↔ mem0 adapters.

Verifies that ``ASOFTLLM`` / ``ASOFTEmbedding`` correctly
translate between mem0's sync OpenAI-style contract and ASOFT AI Services's
async ``Msg`` / ``ContentBlock`` / ``EmbeddingResponse`` shapes, and
that ``register_with_mem0`` plugs them into mem0's factories.
"""
import asyncio
import json
import unittest
from typing import Any

from Providers.credential import DashScopeCredential
from Providers.modelBSN.embedding import EmbeddingModelBase, EmbeddingResponse
from Runtime.message import (
    Msg,
    TextBlock,
    ThinkingBlock,
    ToolCallBlock,
)
from Runtime.middleware._longterm_memory import (
    ASOFTEmbedding,
    ASOFTLLM,
    _convert_messages_to_asoft,
    _parse_chat_response,
    build_mem0_config,
)
from Providers.modelLLM.model import ChatResponse
from utils import MockModel


# ----------------------------------------------------------------------
# Pure helpers
# ----------------------------------------------------------------------


class TestConvertMessages(unittest.TestCase):
    """Tests for converting mem0 dict messages into ASOFT AI Services messages."""

    def test_three_roles_map_to_correct_role(self) -> None:
        """System, user, and assistant roles should be preserved."""
        msgs = _convert_messages_to_asoft(
            [
                {"role": "system", "content": "you are helpful"},
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hello"},
            ],
        )
        self.assertEqual(
            [m.role for m in msgs],
            ["system", "user", "assistant"],
        )
        self.assertTrue(all(isinstance(m, Msg) for m in msgs))
        self.assertEqual(msgs[1].get_text_content(), "hi")

    def test_unknown_role_dropped(self) -> None:
        """Unsupported message roles should be skipped."""
        msgs = _convert_messages_to_asoft(
            [
                {"role": "tool", "content": "noise"},
                {"role": "user", "content": "real"},
            ],
        )
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0].role, "user")


class TestParseChatResponse(unittest.TestCase):
    """Tests for converting ASOFT AI Services chat responses into mem0 output."""

    def _resp(self, blocks: list) -> ChatResponse:
        """Build a final chat response from content blocks."""
        return ChatResponse(content=blocks, is_last=True)

    def test_text_only_returns_string(self) -> None:
        """Plain text responses should become plain strings."""
        resp = self._resp([TextBlock(type="text", text="answer")])
        self.assertEqual(_parse_chat_response(resp, has_tool=False), "answer")

    def test_thinking_prefixed_to_text(self) -> None:
        """Thinking blocks should be preserved before visible text."""
        resp = self._resp(
            [
                ThinkingBlock(type="thinking", thinking="hmm"),
                TextBlock(type="text", text="final"),
            ],
        )
        out = _parse_chat_response(resp, has_tool=False)
        self.assertIn("hmm", out)
        self.assertIn("final", out)
        # thinking comes first to mirror v1 order
        self.assertLess(out.index("hmm"), out.index("final"))

    def test_tool_call_with_json_string_input(self) -> None:
        """v2 stores ToolCallBlock.input as a JSON string — adapter
        must parse it back to a dict for mem0."""
        resp = self._resp(
            [
                TextBlock(type="text", text="calling tool"),
                ToolCallBlock(
                    type="tool_call",
                    id="call_1",
                    name="lookup",
                    input=json.dumps({"q": "alice"}),
                ),
            ],
        )
        out = _parse_chat_response(resp, has_tool=True)
        self.assertEqual(out["content"], "calling tool")
        self.assertEqual(
            out["tool_calls"],
            [{"name": "lookup", "arguments": {"q": "alice"}}],
        )

    def test_tool_call_with_malformed_input_keeps_raw(self) -> None:
        """Malformed JSON tool inputs should remain as raw strings."""
        resp = self._resp(
            [
                ToolCallBlock(
                    type="tool_call",
                    id="call_2",
                    name="lookup",
                    input="not json",
                ),
            ],
        )
        out = _parse_chat_response(resp, has_tool=True)
        self.assertEqual(out["tool_calls"][0]["arguments"], "not json")

    def test_empty_content(self) -> None:
        """Empty responses should convert to the empty mem0 shapes."""
        resp = self._resp([])
        self.assertEqual(_parse_chat_response(resp, has_tool=False), "")
        self.assertEqual(
            _parse_chat_response(resp, has_tool=True),
            {"content": "", "tool_calls": []},
        )


# ----------------------------------------------------------------------
# ASOFTLLM end-to-end (fake ASOFT AI Services model on caller event loop)
# ----------------------------------------------------------------------


class _CurrentEventLoopTestCase(unittest.TestCase):
    """Provides a current event loop for the adapter's sync bridge."""

    _event_loop: asyncio.AbstractEventLoop
    _previous_event_loop: asyncio.AbstractEventLoop | None

    def setUp(self) -> None:
        """Install a fresh event loop for each sync-bridge test."""
        super().setUp()
        try:
            self._previous_event_loop = asyncio.get_event_loop()
        except RuntimeError:
            self._previous_event_loop = None
        self._event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._event_loop)

    def tearDown(self) -> None:
        """Restore the previous event loop after each test."""
        asyncio.set_event_loop(self._previous_event_loop)
        self._event_loop.close()
        super().tearDown()


class _RecordingMockChatModel(MockModel):
    """Captures the ``messages`` arg so we can assert the v2 Msg
    objects mem0's dict messages were converted into."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the recording model."""
        super().__init__(*args, **kwargs)
        self.received_messages: list[list[Msg]] = []

    async def _call_api(self, *args: Any, **kwargs: Any) -> Any:
        """Record delivered messages before delegating to MockModel."""
        self.received_messages.append(list(kwargs.get("messages") or []))
        return await super()._call_api(*args, **kwargs)


class TestASOFTLLM(_CurrentEventLoopTestCase):
    """End-to-end tests for the mem0 LLM adapter."""

    def test_constructor_rejects_non_chatmodel(self) -> None:
        """The LLM adapter should reject non-ASOFT AI Services chat models."""
        with self.assertRaises(TypeError):
            ASOFTLLM(config={"model": object()})

    def test_constructor_requires_model(self) -> None:
        """The LLM adapter should require a model config entry."""
        with self.assertRaises(ValueError):
            ASOFTLLM(config={})

    def test_generate_response_routes_through_asoft_model(self) -> None:
        """mem0 generation should call the wrapped ASOFT AI Services model."""
        model = _RecordingMockChatModel()
        model.set_responses(
            [
                ChatResponse(
                    content=[TextBlock(type="text", text="from ASOFT")],
                    is_last=True,
                ),
            ],
        )
        llm = ASOFTLLM(config={"model": model})

        result = llm.generate_response(
            [
                {"role": "system", "content": "sys"},
                {"role": "user", "content": "hello"},
            ],
        )
        self.assertEqual(result, "from ASOFT")
        # The dict messages were converted to Msg objects with the
        # correct roles preserved.
        delivered = model.received_messages[0]
        self.assertEqual([m.role for m in delivered], ["system", "user"])

    def test_generate_response_with_tools(self) -> None:
        """Tool-call responses should be converted to mem0's tool shape."""
        model = _RecordingMockChatModel()
        model.set_responses(
            [
                ChatResponse(
                    content=[
                        ToolCallBlock(
                            type="tool_call",
                            id="call_3",
                            name="search",
                            input=json.dumps({"q": "x"}),
                        ),
                    ],
                    is_last=True,
                ),
            ],
        )
        llm = ASOFTLLM(config={"model": model})

        result = llm.generate_response(
            [{"role": "user", "content": "find x"}],
            tools=[{"name": "search"}],
        )
        self.assertIsInstance(result, dict)
        self.assertEqual(
            result["tool_calls"],
            [{"name": "search", "arguments": {"q": "x"}}],
        )

    def test_streaming_response_drained_to_last_chunk(self) -> None:
        """When the ASOFT AI Services model streams, the adapter must
        consume all chunks and use the last (which carries the
        complete content per ASOFT AI Services's streaming contract)."""
        model = _RecordingMockChatModel()
        # MockModel.set_responses with a list-of-list triggers stream mode
        model.set_responses(
            [
                [
                    ChatResponse(
                        content=[TextBlock(type="text", text="part 1")],
                        is_last=False,
                    ),
                    ChatResponse(
                        content=[TextBlock(type="text", text="final")],
                        is_last=True,
                    ),
                ],
            ],
        )
        llm = ASOFTLLM(config={"model": model})
        result = llm.generate_response(
            [{"role": "user", "content": "stream"}],
        )
        self.assertEqual(result, "final")

    def test_empty_messages_raises(self) -> None:
        """Dropping all unsupported messages should raise ValueError."""
        llm = ASOFTLLM(config={"model": _RecordingMockChatModel()})
        with self.assertRaises(ValueError):
            llm.generate_response([{"role": "tool", "content": "ignored"}])


# ----------------------------------------------------------------------
# ASOFTEmbedding
# ----------------------------------------------------------------------


class _FakeEmbeddingModel(EmbeddingModelBase):
    """Minimal embedding model that records requested texts."""

    def __init__(self) -> None:
        """Initialize the fake embedding model."""
        super().__init__(
            credential=DashScopeCredential(api_key="fake"),
            model="fake-embed",
            parameters=self.Parameters(dimensions=3),
            context_size=8192,
            batch_size=10,
            max_retries=0,
            retry_delay=0.0,
        )
        self.received: list[list[str]] = []

    async def _call_api(
        self,
        inputs: list[str],
        **kwargs: Any,
    ) -> EmbeddingResponse:
        """Return a fixed vector for every input text."""
        self.received.append(list(inputs))
        return EmbeddingResponse(
            embeddings=[[0.1, 0.2, 0.3] for _ in inputs],
            source="api",
        )


class TestASOFTEmbedding(_CurrentEventLoopTestCase):
    """Tests for the mem0 embedding adapter."""

    def test_constructor_validation(self) -> None:
        """The embedding adapter should validate model config."""
        with self.assertRaises(ValueError):
            ASOFTEmbedding(config={})
        with self.assertRaises(TypeError):
            ASOFTEmbedding(config={"model": object()})

    def test_embed_single_string(self) -> None:
        """Single-string inputs should be wrapped before model calls."""
        model = _FakeEmbeddingModel()
        emb = ASOFTEmbedding(config={"model": model})
        result = emb.embed("hello")
        self.assertEqual(result, [0.1, 0.2, 0.3])
        # The string was wrapped into a list before reaching the model.
        self.assertEqual(model.received, [["hello"]])

    def test_embed_list_of_strings_returns_first(self) -> None:
        """mem0's contract is that ``embed`` returns ONE vector. We
        return the first."""
        model = _FakeEmbeddingModel()
        emb = ASOFTEmbedding(config={"model": model})
        result = emb.embed(["a", "b"])
        self.assertEqual(result, [0.1, 0.2, 0.3])
        self.assertEqual(model.received, [["a", "b"]])


# ----------------------------------------------------------------------
# Factory registration
# ----------------------------------------------------------------------


class TestBuildMem0Config(unittest.TestCase):
    """``build_mem0_config`` must bypass mem0's hardcoded provider
    whitelist and emit a config that names the ASOFT AI Services adapter."""

    def test_models_only_produces_fresh_config(self) -> None:
        """Models-only construction should create ASOFT AI Services providers."""
        chat = MockModel()
        emb = _FakeEmbeddingModel()
        cfg = build_mem0_config(chat_model=chat, embedding_model=emb)

        self.assertEqual(cfg.llm.provider, "ASOFT")
        self.assertEqual(cfg.embedder.provider, "ASOFT")
        self.assertIs(cfg.llm.config["model"], chat)
        self.assertIs(cfg.embedder.config["model"], emb)

    def test_models_only_requires_both(self) -> None:
        """Models-only construction should require chat and embedding."""
        with self.assertRaises(ValueError):
            build_mem0_config(chat_model=MockModel())
        with self.assertRaises(ValueError):
            build_mem0_config(embedding_model=_FakeEmbeddingModel())
        with self.assertRaises(ValueError):
            build_mem0_config()

    def test_base_config_with_both_models_preserves_other_fields(
        self,
    ) -> None:
        """When a ``mem0_config`` base is given, vector_store /
        history_db / etc. should survive — only .llm and .embedder
        are rewired to the ASOFT AI Services adapters."""
        from mem0.configs.base import MemoryConfig

        base = MemoryConfig(history_db_path="/tmp/custom_history.db")
        original_vs = base.vector_store

        chat = MockModel()
        emb = _FakeEmbeddingModel()
        cfg = build_mem0_config(
            chat_model=chat,
            embedding_model=emb,
            mem0_config=base,
        )

        self.assertEqual(cfg.llm.provider, "ASOFT")
        self.assertIs(cfg.llm.config["model"], chat)
        self.assertEqual(cfg.embedder.provider, "ASOFT")
        self.assertIs(cfg.embedder.config["model"], emb)
        # Non-llm/embedder fields preserved.
        self.assertEqual(cfg.history_db_path, "/tmp/custom_history.db")
        self.assertIs(cfg.vector_store, original_vs)

    def test_base_config_with_only_chat_model_partial_override(
        self,
    ) -> None:
        """Partial override: chat_model alone replaces .llm but
        leaves .embedder untouched (whatever the base config had)."""
        from mem0.configs.base import MemoryConfig

        base = MemoryConfig()  # base has the default openai embedder
        original_embedder = base.embedder

        cfg = build_mem0_config(
            chat_model=MockModel(),
            mem0_config=base,
        )
        self.assertEqual(cfg.llm.provider, "ASOFT")
        # Embedder unchanged from base — still mem0's openai default.
        self.assertIs(cfg.embedder, original_embedder)

    def test_base_config_alone_is_pass_through(self) -> None:
        """``mem0_config=base`` with no models is just a pass-through —
        registration still happens (cheap) but no fields change."""
        from mem0.configs.base import MemoryConfig

        base = MemoryConfig()
        cfg = build_mem0_config(mem0_config=base)
        self.assertIs(cfg, base)

    def test_registers_adapter_in_factory(self) -> None:
        """The helper side-effect: mem0's factory dicts now know how
        to resolve provider='ASOFT'."""
        from mem0.utils.factory import EmbedderFactory, LlmFactory

        build_mem0_config(
            chat_model=MockModel(),
            embedding_model=_FakeEmbeddingModel(),
        )
        self.assertIn("ASOFT", LlmFactory.provider_to_class)
        self.assertIn("ASOFT", EmbedderFactory.provider_to_class)

    def test_naive_from_config_path_still_rejected(self) -> None:
        """Sanity check: confirm WHY the helper exists — calling
        ``MemoryConfig`` with ``provider='ASOFT'`` directly DOES
        raise, which is the failure ``build_mem0_config`` works around."""
        from mem0.configs.base import MemoryConfig
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            MemoryConfig(
                llm={
                    "provider": "ASOFT",
                    "config": {"model": MockModel()},
                },
                embedder={
                    "provider": "ASOFT",
                    "config": {"model": _FakeEmbeddingModel()},
                },
            )
