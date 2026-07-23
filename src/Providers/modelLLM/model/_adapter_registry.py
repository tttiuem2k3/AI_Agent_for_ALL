# -*- coding: utf-8 -*-
"""Registry for selecting a concrete chat-model runtime adapter."""
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from ._base import ChatModelBase
from ._model_card import ModelCard
from ._anthropic import AnthropicChatModel
from ._dashscope import DashScopeChatModel
from ._deepseek import DeepSeekChatModel
from ._gemini import GeminiChatModel
from ._moonshot import MoonshotChatModel
from ._ollama import OllamaChatModel
from ._openai_chat import OpenAIChatModel
from ._openai_response import OpenAIResponseModel
from ._xai import XAIChatModel


@dataclass(frozen=True)
class ChatModelAdapter:
    """A registered model runtime and its compatible credentials."""

    key: str
    model_class: type[ChatModelBase]
    credential_types: frozenset[str]


class ChatModelAdapterRegistry:
    """Resolve model runtimes independently from credential deserialization."""

    _adapters = {
        adapter.key: adapter
        for adapter in (
            ChatModelAdapter(
                "anthropic_chat",
                AnthropicChatModel,
                frozenset({"anthropic_credential"}),
            ),
            ChatModelAdapter(
                "dashscope_chat",
                DashScopeChatModel,
                frozenset({"dashscope_credential"}),
            ),
            ChatModelAdapter(
                "deepseek_chat",
                DeepSeekChatModel,
                frozenset({"deepseek_credential"}),
            ),
            ChatModelAdapter(
                "gemini_chat",
                GeminiChatModel,
                frozenset({"gemini_credential"}),
            ),
            ChatModelAdapter(
                "moonshot_chat",
                MoonshotChatModel,
                frozenset({"moonshot_credential"}),
            ),
            ChatModelAdapter(
                "ollama_chat",
                OllamaChatModel,
                frozenset({"ollama_credential"}),
            ),
            ChatModelAdapter(
                "openai_chat",
                OpenAIChatModel,
                frozenset({"openai_credential"}),
            ),
            ChatModelAdapter(
                "openai_response",
                OpenAIResponseModel,
                frozenset({"openai_credential"}),
            ),
            ChatModelAdapter(
                "xai_chat",
                XAIChatModel,
                frozenset({"xai_credential"}),
            ),
        )
    }
    _credential_defaults = {
        "anthropic_credential": "anthropic_chat",
        "dashscope_credential": "dashscope_chat",
        "deepseek_credential": "deepseek_chat",
        "gemini_credential": "gemini_chat",
        "moonshot_credential": "moonshot_chat",
        "ollama_credential": "ollama_chat",
        "openai_credential": "openai_chat",
        "xai_credential": "xai_chat",
    }

    @classmethod
    def resolve(cls, adapter_key: str) -> ChatModelAdapter:
        """Return a registered adapter or raise a configuration error."""
        adapter = cls._adapters.get(adapter_key)
        if adapter is None:
            raise ValueError(f"Unknown chat model adapter {adapter_key!r}.")
        return adapter

    @classmethod
    def default_for_credential(cls, credential_type: str) -> ChatModelAdapter:
        """Return the legacy-compatible default for a credential type."""
        adapter_key = cls._credential_defaults.get(credential_type)
        if adapter_key is None:
            raise ValueError(
                f"Credential type {credential_type!r} has no chat model adapter.",
            )
        return cls.resolve(adapter_key)

    @classmethod
    def select(
        cls,
        model_adapter: str | None,
        legacy_type: str | None,
        credential_type: str,
    ) -> tuple[ChatModelAdapter, bool]:
        """Select an adapter and report whether the selection is explicit.

        ``legacy_type`` historically contained a credential discriminator.
        For compatibility, a registered adapter key in that field is also
        accepted while credential discriminator values keep their old
        default behavior.
        """
        adapter_key = model_adapter
        if adapter_key is None and legacy_type in cls._adapters:
            adapter_key = legacy_type

        explicit = adapter_key is not None
        adapter = (
            cls.resolve(adapter_key)
            if adapter_key is not None
            else cls.default_for_credential(credential_type)
        )
        if credential_type not in adapter.credential_types:
            raise ValueError(
                f"Chat model adapter {adapter.key!r} is not compatible with "
                f"credential type {credential_type!r}.",
            )
        return adapter, explicit

    @classmethod
    def validate(
        cls,
        adapter: ChatModelAdapter,
        model: str,
        parameters: dict[str, Any],
        strict_parameters: bool,
    ) -> ModelCard:
        """Validate model membership and adapter-specific parameters."""
        cards = cls._model_cards(adapter.key)
        card = cards.get(model)
        if card is None:
            raise ValueError(
                f"Model {model!r} is not supported by chat model adapter "
                f"{adapter.key!r}.",
            )

        if strict_parameters:
            allowed = set(
                card.parameter_schema.get("properties", {}).keys(),
            )
            unknown = sorted(set(parameters) - allowed)
            if unknown:
                raise ValueError(
                    f"Model {model!r} on adapter {adapter.key!r} does not "
                    f"support parameter(s): {', '.join(unknown)}.",
                )
        return card

    @classmethod
    @lru_cache(maxsize=None)
    def _model_cards(cls, adapter_key: str) -> dict[str, ModelCard]:
        adapter = cls.resolve(adapter_key)
        return {card.name: card for card in adapter.model_class.list_models()}

    @classmethod
    def list_adapters(cls) -> tuple[ChatModelAdapter, ...]:
        """Return all registered adapters for seed/postflight generation."""
        return tuple(cls._adapters.values())
