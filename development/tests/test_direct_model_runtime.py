# -*- coding: utf-8 -*-
"""DM-2 contract tests for session-native DirectModel runtime."""
import asyncio
from contextlib import asynccontextmanager

import pytest
import fakeredis.aioredis
import httpx
from pydantic import ValidationError

from Service.app._router._schema import (
    ChatRequest,
    CreateSessionRequest,
    UpdateSessionRequest,
)
from Service.app._router._session import create_session, update_session
from Service.app._service import _chat as chat_module
from Service.app._service._chat import ChatService
from Service.app._service._toolkit import get_toolkit
from Service.app._service._erpx_tool_gateway import (
    ERPXToolFactory,
    ERPXToolGatewayClient,
)
from Service.app.storage import (
    AgentRuntimeProfile,
    CapabilityManifestV2,
    ChatModelConfig,
    DirectModelRuntimeProfile,
    RedisStorage,
    SessionConfig,
    SessionRecord,
    compute_capability_manifest_v2_hash,
)
from Service.app.storage._model._capability import ToolCapability


def _manifest_v2(
    *,
    subject_id: str = "dm_subject_01",
    tools: list[ToolCapability] | None = None,
) -> CapabilityManifestV2:
    payload = {
        "manifest_version": "2",
        "subject_type": "DirectModel",
        "subject_id": subject_id,
        "user_id": "ERP_USER",
        "division_id": "DIV01",
        "tools": [
            tool.model_dump(mode="json")
            for tool in (tools or [])
        ],
        "skills": [],
    }
    return CapabilityManifestV2(
        **payload,
        hash=compute_capability_manifest_v2_hash(payload),
    )


def _direct_profile(
    *,
    subject_id: str = "dm_subject_01",
) -> DirectModelRuntimeProfile:
    return DirectModelRuntimeProfile(
        base_capabilities=_manifest_v2(subject_id=subject_id),
    )


def test_legacy_agent_session_gets_runtime_profile() -> None:
    session = SessionRecord(
        user_id="runtime-key",
        agent_id="agent-01",
        config=SessionConfig(workspace_id="workspace-01"),
    )

    assert isinstance(session.runtime_profile, AgentRuntimeProfile)
    assert session.runtime_profile.agent_id == "agent-01"
    assert session.runtime_subject_id is None
    assert session.runtime_owner_id == "agent-01"


def test_direct_session_has_no_agent_identity() -> None:
    profile = _direct_profile()
    session = SessionRecord(
        user_id="runtime-key",
        agent_id=None,
        runtime_subject_id="dm_subject_01",
        runtime_profile=profile,
        config=SessionConfig(
            workspace_id="workspace-01",
            effective_capabilities=profile.base_capabilities,
        ),
    )

    assert session.agent_id is None
    assert session.runtime_owner_id == "direct_model__dm_subject_01"


def test_direct_session_rejects_mixed_agent_shape() -> None:
    with pytest.raises(ValidationError):
        SessionRecord(
            user_id="runtime-key",
            agent_id="synthetic-agent",
            runtime_subject_id="dm_subject_01",
            runtime_profile=_direct_profile(),
            config=SessionConfig(workspace_id="workspace-01"),
        )


def test_manifest_v2_recomputes_hash() -> None:
    valid = _manifest_v2()
    assert valid.hash == valid.computed_hash()

    with pytest.raises(ValidationError):
        CapabilityManifestV2(
            **valid.canonical_payload(),
            hash="0" * 64,
        )


def test_session_request_keeps_legacy_agent_contract() -> None:
    request = CreateSessionRequest(agent_id="agent-01")

    assert isinstance(request.runtime_profile, AgentRuntimeProfile)
    assert request.runtime_profile.agent_id == "agent-01"


def test_session_request_accepts_explicit_direct_profile() -> None:
    request = CreateSessionRequest(
        runtime_subject_id="dm_subject_01",
        runtime_profile=_direct_profile(),
    )

    assert request.agent_id is None
    assert isinstance(request.runtime_profile, DirectModelRuntimeProfile)


def test_update_session_can_expand_trusted_direct_base_manifest() -> None:
    async def _run() -> None:
        old_profile = _direct_profile()
        session = SessionRecord(
            user_id="runtime-key",
            agent_id=None,
            runtime_subject_id="dm_subject_01",
            runtime_profile=old_profile,
            config=SessionConfig(
                workspace_id="workspace-01",
                effective_capabilities=old_profile.base_capabilities,
            ),
        )
        tool = ToolCapability(
            tool_id="ON_TEST",
            function_name="ONTest",
            tool_type="Builtin",
            tool_group="Test",
            description_for_llm="Test tool",
            input_schema={"type": "object", "properties": {}},
            is_read_only=True,
            require_approval=False,
        )
        expanded_manifest = _manifest_v2(tools=[tool])
        expanded_profile = DirectModelRuntimeProfile(
            base_capabilities=expanded_manifest,
        )

        class _Storage:
            async def get_session(self, user_id, agent_id, session_id):
                return session

            async def upsert_session(self, **kwargs):
                return SessionRecord(
                    user_id=kwargs["user_id"],
                    agent_id=kwargs["agent_id"],
                    runtime_subject_id=kwargs["runtime_subject_id"],
                    runtime_profile=kwargs["runtime_profile"],
                    config=kwargs["config"],
                    state=kwargs["state"],
                    id=kwargs["session_id"],
                )

        updated = await update_session(
            session_id=session.id,
            body=UpdateSessionRequest(
                runtime_profile=expanded_profile,
                effective_capabilities=expanded_manifest,
            ),
            agent_id=None,
            runtime_subject_id="dm_subject_01",
            user_id="runtime-key",
            storage=_Storage(),
        )
        assert isinstance(
            updated.runtime_profile,
            DirectModelRuntimeProfile,
        )
        assert [item.tool_id for item in
                updated.runtime_profile.base_capabilities.tools] == ["ON_TEST"]

    asyncio.run(_run())


def test_direct_gateway_payload_uses_runtime_subject_without_agent() -> None:
    async def _handler(request: httpx.Request) -> httpx.Response:
        payload = __import__("json").loads(request.content)
        assert payload["execution_mode"] == "DirectModel"
        assert payload["runtime_subject_id"] == "dm_subject_01"
        assert payload["agent_apk"] is None
        return httpx.Response(
            200,
            json={
                "status": "Succeeded",
                "execution_id": "exec-01",
                "message": "ok",
            },
        )

    async def _run() -> None:
        client = ERPXToolGatewayClient(
            base_url="https://services.test",
            api_key="secret",
            transport=httpx.MockTransport(_handler),
        )
        result = await client.execute(
            "ON_TEST",
            "tool-call-01",
            "run-01",
            "session-01",
            "DirectModel",
            "dm_subject_01",
            None,
            "ERP_USER",
            "DIV01",
            "0" * 64,
            {},
        )
        assert result["execution_id"] == "exec-01"

    asyncio.run(_run())


def test_direct_tool_factory_binds_v2_hash_and_subject() -> None:
    async def _run() -> None:
        tool = ToolCapability(
            tool_id="ON_TEST",
            function_name="ONTest",
            tool_type="ServicesApi",
            tool_group="Test",
            description_for_llm="Test service tool",
            input_schema={"type": "object", "properties": {}},
            is_read_only=True,
            require_approval=False,
        )
        manifest = _manifest_v2(tools=[tool])
        profile = DirectModelRuntimeProfile(base_capabilities=manifest)
        session = SessionRecord(
            user_id="runtime-key",
            agent_id=None,
            runtime_subject_id="dm_subject_01",
            runtime_profile=profile,
            config=SessionConfig(
                workspace_id="workspace-01",
                runtime_run_id="run-01",
                effective_capabilities=manifest,
            ),
        )

        class _Storage:
            async def get_session(self, user_id, agent_id, session_id):
                return session

        class _Client:
            async def execute(self, *args):
                return {"status": "Succeeded"}

        tools = await ERPXToolFactory(_Storage(), _Client())(
            "runtime-key",
            None,
            session.id,
        )
        assert len(tools) == 1
        assert tools[0]._runtime_subject_id == "dm_subject_01"
        assert tools[0]._agent_apk is None
        assert tools[0]._capability_hash == manifest.hash

    asyncio.run(_run())


def test_create_direct_session_does_not_provision_agent() -> None:
    class _Storage:
        get_agent_called = False
        record = None

        async def get_agent(self, user_id, agent_id):
            self.get_agent_called = True
            raise AssertionError("DirectModel must not load AgentRecord")

        async def upsert_session(self, **kwargs):
            self.record = SessionRecord(
                user_id=kwargs["user_id"],
                agent_id=kwargs["agent_id"],
                runtime_subject_id=kwargs["runtime_subject_id"],
                runtime_profile=kwargs["runtime_profile"],
                config=kwargs["config"],
            )
            return self.record

    async def _run() -> None:
        profile = _direct_profile()
        storage = _Storage()
        response = await create_session(
            body=CreateSessionRequest(
                runtime_subject_id="dm_subject_01",
                runtime_profile=profile,
            ),
            user_id="runtime-key",
            storage=storage,
        )
        assert storage.get_agent_called is False
        assert storage.record.agent_id is None
        assert response.session_id == storage.record.id
        assert response.runtime_subject_id == "dm_subject_01"

    asyncio.run(_run())


def test_chat_request_requires_one_runtime_identity() -> None:
    ChatRequest(
        agent_id="agent-01",
        session_id="session-01",
        input=None,
    )
    ChatRequest(
        runtime_subject_id="dm_subject_01",
        session_id="session-01",
        input=None,
    )

    with pytest.raises(ValidationError):
        ChatRequest(session_id="session-01", input=None)
    with pytest.raises(ValidationError):
        ChatRequest(
            agent_id="agent-01",
            runtime_subject_id="dm_subject_01",
            session_id="session-01",
            input=None,
        )


def test_redis_indexes_direct_session_by_runtime_subject() -> None:
    async def _run() -> None:
        storage = RedisStorage.__new__(RedisStorage)
        storage._client = fakeredis.aioredis.FakeRedis(
            decode_responses=True,
        )
        storage.key_ttl = None
        storage.key_config = RedisStorage.KeyConfig()

        profile = _direct_profile()
        session = await storage.upsert_session(
            user_id="runtime-key",
            agent_id=None,
            runtime_profile=profile,
            runtime_subject_id="dm_subject_01",
            config=SessionConfig(
                workspace_id="workspace-01",
                effective_capabilities=profile.base_capabilities,
            ),
        )

        direct_sessions = await storage.list_sessions(
            "runtime-key",
            "direct_model__dm_subject_01",
        )
        assert [item.id for item in direct_sessions] == [session.id]
        assert direct_sessions[0].agent_id is None

        deleted = await storage.delete_session(
            "runtime-key",
            None,
            session.id,
        )
        assert deleted is True
        assert await storage.list_sessions(
            "runtime-key",
            "direct_model__dm_subject_01",
        ) == []

    asyncio.run(_run())


def test_direct_toolkit_is_fail_closed_without_selected_capabilities() -> None:
    class _Workspace:
        async def list_tools(self):
            return []

        async def list_skills(self):
            return []

        async def list_mcps(self):
            raise AssertionError("DirectModel must not inherit MCP clients")

    class _Background:
        async def list_tools(self, session_id):
            return []

    class _Scheduler:
        async def list_tools(self, **kwargs):
            raise AssertionError("DirectModel must not receive schedules")

    async def _run() -> None:
        profile = _direct_profile()
        session = SessionRecord(
            user_id="runtime-key",
            agent_id=None,
            runtime_subject_id="dm_subject_01",
            runtime_profile=profile,
            config=SessionConfig(
                workspace_id="workspace-01",
                effective_capabilities=profile.base_capabilities,
            ),
        )
        toolkit = await get_toolkit(
            storage=object(),
            workspace=_Workspace(),
            scheduler_manager=_Scheduler(),
            background_task_manager=_Background(),
            message_bus=object(),
            user_id="runtime-key",
            agent_record=None,
            session_record=session,
        )
        names = [
            tool.name
            for group in toolkit.tool_groups
            for tool in group.tools
        ]
        assert names == []
        assert await toolkit.get_skill_instructions() is None

    asyncio.run(_run())


class _FakeStorage:
    def __init__(self, session: SessionRecord) -> None:
        self.session = session
        self.get_agent_called = False
        self.updated_state = None

    async def get_session(self, user_id, agent_id, session_id):
        assert user_id == self.session.user_id
        assert session_id == self.session.id
        return self.session

    async def get_agent(self, user_id, agent_id):
        self.get_agent_called = True
        raise AssertionError("DirectModel must not load AgentRecord")

    async def update_session_state(
        self,
        user_id,
        agent_id,
        session_id,
        state,
    ):
        self.updated_state = state


class _FakeWorkspace:
    workdir = "D:/runtime/direct-model-test"


class _FakeWorkspaceManager:
    def __init__(self) -> None:
        self.owner_id = None

    async def get_workspace(
        self,
        user_id,
        owner_id,
        session_id,
        workspace_id,
    ):
        self.owner_id = owner_id
        return _FakeWorkspace()


class _FakeMessageBus:
    @asynccontextmanager
    async def acquire_lock(self, key, ttl_secs):
        yield

    async def log_trim(self, key):
        return None


class _CapturingAgent:
    kwargs = None

    def __init__(self, **kwargs) -> None:
        type(self).kwargs = kwargs
        self.name = kwargs["name"]
        self.state = kwargs["state"]

    async def reply_stream(self, inputs):
        if False:
            yield inputs


def test_chat_service_constructs_ephemeral_direct_agent(
    monkeypatch,
) -> None:
    profile = _direct_profile()
    session = SessionRecord(
        user_id="runtime-key",
        agent_id=None,
        runtime_subject_id="dm_subject_01",
        runtime_profile=profile,
        config=SessionConfig(
            workspace_id="workspace-01",
            chat_model_config=ChatModelConfig(
                credential_id="credential-01",
                model="model-01",
            ),
            effective_capabilities=profile.base_capabilities,
        ),
    )
    storage = _FakeStorage(session)
    workspace_manager = _FakeWorkspaceManager()

    async def _fake_get_model(user_id, config, model_storage):
        return object()

    async def _fake_get_toolkit(**kwargs):
        assert kwargs["agent_record"] is None
        return object()

    monkeypatch.setattr(chat_module, "get_model", _fake_get_model)
    monkeypatch.setattr(chat_module, "get_toolkit", _fake_get_toolkit)

    service = ChatService(
        storage=storage,
        workspace_manager=workspace_manager,
        scheduler_manager=object(),
        background_task_manager=object(),
        message_bus=_FakeMessageBus(),
        custom_agent_cls=_CapturingAgent,
    )

    asyncio.run(
        service._run_impl(
            user_id="runtime-key",
            session_id=session.id,
            agent_id=None,
            runtime_subject_id="dm_subject_01",
            input_msg=None,
        ),
    )

    assert storage.get_agent_called is False
    assert storage.updated_state is session.state
    assert workspace_manager.owner_id == "direct_model__dm_subject_01"
    assert _CapturingAgent.kwargs["name"] == "DirectModel"
    assert "enterprise assistant" in _CapturingAgent.kwargs["system_prompt"]
