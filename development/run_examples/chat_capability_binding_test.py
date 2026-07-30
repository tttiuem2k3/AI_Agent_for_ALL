# -*- coding: utf-8 -*-
"""Regression tests for ERPX chat capability/session identity binding."""

from unittest import IsolatedAsyncioTestCase

from fastapi import HTTPException

from Runtime.agent import ContextConfig, ReActConfig
from Service.app._router._chat import _refresh_effective_capabilities
from Service.app._router._schema import ChatRequest
from Service.app.storage import (
    AgentData,
    AgentRecord,
    CapabilityManifest,
    SessionConfig,
    SessionRecord,
)


class _Storage:
    def __init__(
        self,
        agent: AgentRecord,
        session: SessionRecord,
    ) -> None:
        self.agent = agent
        self.session = session
        self.updated: dict | None = None

    async def get_session(
        self,
        user_id: str,
        agent_id: str,
        session_id: str,
    ) -> SessionRecord:
        del user_id, agent_id, session_id
        return self.session

    async def get_agent(
        self,
        user_id: str,
        agent_id: str,
    ) -> AgentRecord:
        del user_id, agent_id
        return self.agent

    async def upsert_session(self, **kwargs) -> None:
        self.updated = kwargs


def _manifest(*, erp_user_id: str | None) -> CapabilityManifest:
    return CapabilityManifest(
        agent_apk="agent-apk",
        agent_id="__DM_model",
        user_id=erp_user_id,
        division_id="D1",
        capability_hash="a" * 64,
    )


def _binding() -> tuple[_Storage, str, str]:
    runtime_subject = "erpx:customer:D1:runtime"
    runtime_agent_id = "runtime-agent"
    agent = AgentRecord(
        user_id=runtime_subject,
        data=AgentData(
            name="Direct model",
            system_prompt="Answer the user.",
            context_config=ContextConfig(),
            react_config=ReActConfig(),
            base_capabilities=_manifest(erp_user_id=None),
        ),
    )
    session = SessionRecord(
        user_id=runtime_subject,
        agent_id=runtime_agent_id,
        config=SessionConfig(
            workspace_id="workspace",
            effective_capabilities=_manifest(erp_user_id="ERP_USER"),
        ),
    )
    return _Storage(agent, session), runtime_subject, runtime_agent_id


class TestChatCapabilityBinding(IsolatedAsyncioTestCase):
    async def test_runtime_subject_can_differ_from_erp_user(self) -> None:
        storage, runtime_subject, runtime_agent_id = _binding()
        request = ChatRequest(
            agent_id=runtime_agent_id,
            session_id="session",
            effective_capabilities=_manifest(erp_user_id="ERP_USER"),
            input=None,
        )

        await _refresh_effective_capabilities(
            request,
            runtime_subject,
            storage,  # type: ignore[arg-type]
        )

        self.assertIsNotNone(storage.updated)

    async def test_erp_user_cannot_change_after_session_creation(self) -> None:
        storage, runtime_subject, runtime_agent_id = _binding()
        request = ChatRequest(
            agent_id=runtime_agent_id,
            session_id="session",
            effective_capabilities=_manifest(erp_user_id="OTHER_USER"),
            input=None,
        )

        with self.assertRaises(HTTPException) as raised:
            await _refresh_effective_capabilities(
                request,
                runtime_subject,
                storage,  # type: ignore[arg-type]
            )

        self.assertEqual(raised.exception.status_code, 403)

    async def test_legacy_session_can_bind_erp_user_once(self) -> None:
        storage, runtime_subject, runtime_agent_id = _binding()
        storage.session.config = storage.session.config.model_copy(
            update={"effective_capabilities": None},
        )
        request = ChatRequest(
            agent_id=runtime_agent_id,
            session_id="session",
            effective_capabilities=_manifest(erp_user_id="ERP_USER"),
            input=None,
        )

        await _refresh_effective_capabilities(
            request,
            runtime_subject,
            storage,  # type: ignore[arg-type]
        )

        self.assertEqual(
            storage.updated["config"].effective_capabilities.user_id,
            "ERP_USER",
        )
