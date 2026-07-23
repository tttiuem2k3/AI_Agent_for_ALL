# -*- coding: utf-8 -*-
"""Focused tests for chat model adapter selection and validation."""
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock

from fastapi import HTTPException

from Providers.modelLLM.model import OpenAIChatModel, OpenAIResponseModel
from Service.app._router._session import _ensure_credential_exists
from Service.app._service._model import get_model
from Service.app._service._chat import ChatService
from Service.app.storage import ChatModelConfig


def _storage() -> AsyncMock:
    storage = AsyncMock()
    storage.get_credential.return_value = SimpleNamespace(
        data={
            "type": "openai_credential",
            "id": "credential-1",
            "name": "OpenAI",
            "api_key": "test-only",
        },
    )
    return storage


class ChatModelAdapterSelectionTest(IsolatedAsyncioTestCase):
    """Validate explicit model adapters and legacy fallback behavior."""

    async def test_explicit_response_adapter_is_selected(self) -> None:
        model = await get_model(
            "user-1",
            ChatModelConfig(
                type="openai_credential",
                model_adapter="openai_response",
                credential_id="credential-1",
                model="o4-mini",
                context_size=321_000,
                parameters={"max_tokens": 1024},
            ),
            _storage(),
        )

        self.assertIsInstance(model, OpenAIResponseModel)
        self.assertEqual(model.context_size, 321_000)
        self.assertEqual(model.parameters.max_tokens, 1024)

    async def test_legacy_credential_type_keeps_chat_fallback(self) -> None:
        model = await get_model(
            "user-1",
            ChatModelConfig(
                type="openai_credential",
                credential_id="credential-1",
                model="gpt-4o",
                parameters={"max_tokens": 256},
            ),
            _storage(),
        )

        self.assertIsInstance(model, OpenAIChatModel)

    async def test_legacy_type_accepts_an_adapter_key(self) -> None:
        model = await get_model(
            "user-1",
            ChatModelConfig(
                type="openai_response",
                credential_id="credential-1",
                model="gpt-5.5",
                parameters={"max_tokens": 256},
            ),
            _storage(),
        )

        self.assertIsInstance(model, OpenAIResponseModel)

    async def test_rejects_parameter_hidden_by_model_profile(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            await get_model(
                "user-1",
                ChatModelConfig(
                    model_adapter="openai_response",
                    credential_id="credential-1",
                    model="o4-mini",
                    parameters={"max_tokens": 256, "temperature": 0.7},
                ),
                _storage(),
            )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("temperature", ctx.exception.detail)

    async def test_gpt_55_rejects_unsupported_temperature(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            await get_model(
                "user-1",
                ChatModelConfig(
                    model_adapter="openai_response",
                    credential_id="credential-1",
                    model="gpt-5.5",
                    parameters={"max_tokens": 256, "temperature": 2.0},
                ),
                _storage(),
            )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("temperature", ctx.exception.detail)

    async def test_rejects_incompatible_credential(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            await get_model(
                "user-1",
                ChatModelConfig(
                    model_adapter="anthropic_chat",
                    credential_id="credential-1",
                    model="claude-sonnet-4-6",
                ),
                _storage(),
            )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("not compatible", ctx.exception.detail)

    async def test_rejects_model_outside_adapter_catalog(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            await get_model(
                "user-1",
                ChatModelConfig(
                    model_adapter="openai_response",
                    credential_id="credential-1",
                    model="not-a-real-model",
                ),
                _storage(),
            )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("not supported", ctx.exception.detail)

    async def test_session_validation_fails_before_provider_call(self) -> None:
        storage = _storage()
        with self.assertRaises(HTTPException) as ctx:
            await _ensure_credential_exists(
                storage,
                "user-1",
                ChatModelConfig(
                    model_adapter="openai_response",
                    credential_id="credential-1",
                    model="o4-mini",
                    parameters={"top_p": 0.8},
                ),
            )

        self.assertEqual(ctx.exception.status_code, 400)
        storage.list_credentials.assert_not_awaited()


class ChatRunErrorSanitizationTest(TestCase):
    """Terminal errors must be stable and contain no raw provider detail."""

    def test_provider_exception_is_sanitized(self) -> None:
        raw_secret = "api_key=should-never-be-published"
        code, message, retryable = ChatService._sanitize_run_error(
            ValueError(raw_secret),
        )

        self.assertEqual(code, "model_execution_failed")
        self.assertTrue(retryable)
        self.assertNotIn(raw_secret, message)

    def test_invalid_runtime_configuration_is_not_retryable(self) -> None:
        code, _, retryable = ChatService._sanitize_run_error(
            HTTPException(status_code=400, detail="raw provider response"),
        )

        self.assertEqual(code, "runtime_configuration_invalid")
        self.assertFalse(retryable)

    def test_provider_bad_request_exposes_only_safe_parameter_name(self) -> None:
        error = ValueError("raw response with secret")
        error.status_code = 400
        error.body = {"error": {"param": "temperature"}}

        code, message, retryable = ChatService._sanitize_run_error(error)

        self.assertEqual(code, "provider_request_invalid")
        self.assertIn("temperature", message)
        self.assertNotIn("raw response", message)
        self.assertFalse(retryable)


if __name__ == "__main__":
    import unittest

    unittest.main()
