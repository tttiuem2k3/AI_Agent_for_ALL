# -*- coding: utf-8 -*-
"""DM-2 contract tests for session-native DirectModel runtime."""
import asyncio
import sys
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
from types import SimpleNamespace

import pytest
import fakeredis.aioredis
import httpx
from pydantic import BaseModel, ValidationError

from Capabilities.tool._builtin._bash_parser import BashCommandParser
from Capabilities.tool._builtin._backend import ExecResult
from Capabilities.tool._builtin._grep import Grep
from Capabilities.tool import ToolBase, ToolChunk, ToolResponse, Toolkit
from Capabilities.workspace import WorkspaceBase
from Providers.credential import OpenAICredential
from Providers.modelLLM.model import ChatResponse, FinishedReason
from Providers.modelLLM.model._openai_chat import OpenAIChatModel
from Runtime.message import (
    AssistantMsg,
    TextBlock,
    ToolCallBlock,
    ToolCallState,
    ToolResultBlock,
    ToolResultState,
)
from Runtime.agent import Agent
from Runtime.middleware import MiddlewareBase
from Capabilities.permission import PermissionBehavior, PermissionDecision


def test_openai_chat_model_reuses_lazy_client(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    from types import SimpleNamespace

    created = []

    class FakeClient:
        def __init__(self, **kwargs):
            created.append(kwargs)

    monkeypatch.setitem(
        sys.modules,
        "openai",
        SimpleNamespace(AsyncClient=FakeClient),
    )
    credential = OpenAICredential(api_key="test-key")
    model = OpenAIChatModel(credential=credential, model="gpt-test")

    assert model._get_client() is model._get_client()
    assert len(created) == 1
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


def test_grep_rejects_negative_pagination_values() -> None:
    async def _run() -> None:
        grep = Grep()

        head_limit_result = await grep.call(
            pattern="needle",
            head_limit=-1,
        )
        offset_result = await grep.call(
            pattern="needle",
            offset=-1,
        )

        assert head_limit_result.state == "error"
        assert "head_limit must be non-negative" in (
            head_limit_result.content[0].text
        )
        assert offset_result.state == "error"
        assert "offset must be non-negative" in offset_result.content[0].text

    asyncio.run(_run())


def test_bash_parser_treats_mutating_find_as_not_read_only() -> None:
    parser = BashCommandParser()

    assert parser.is_read_only_command("find . -name '*.py'") is True
    assert parser.is_read_only_command("find . -name '*.tmp' -delete") is False
    assert parser.is_read_only_command(
        r"find . -name '*.tmp' -exec rm {} \;",
    ) is False


def test_chat_response_defaults_finished_reason_per_instance() -> None:
    first = ChatResponse(content=[], is_last=True)
    second = ChatResponse(content=[], is_last=True)

    assert first.finished_reason == FinishedReason.COMPLETED
    assert second.finished_reason == FinishedReason.COMPLETED
    first.finished_reason = FinishedReason.INTERRUPTED
    assert second.finished_reason == FinishedReason.COMPLETED


def test_openai_chat_uses_max_completion_tokens(monkeypatch) -> None:
    captured: dict = {}

    class _FakeCompletions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(choices=[], usage=None, id="resp-01")

    class _FakeClient:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(
                completions=_FakeCompletions(),
            )

    monkeypatch.setitem(
        sys.modules,
        "openai",
        SimpleNamespace(AsyncClient=_FakeClient),
    )

    async def _run() -> None:
        model = OpenAIChatModel(
            credential=OpenAICredential(api_key="secret"),
            model="gpt-test",
            parameters=OpenAIChatModel.Parameters(max_tokens=123),
            stream=False,
        )
        await model._call_api("gpt-test", [])

    asyncio.run(_run())

    assert captured["max_completion_tokens"] == 123
    assert "max_tokens" not in captured


def test_tool_response_preserves_error_state_after_later_chunks() -> None:
    response = ToolResponse()

    response.append_chunk(ToolChunk(content=[], state=ToolResultState.ERROR))
    response.append_chunk(ToolChunk(content=[], state=ToolResultState.DENIED))
    response.append_chunk(
        ToolChunk(content=[], state=ToolResultState.INTERRUPTED),
    )

    assert response.state == ToolResultState.ERROR


def test_workspace_base_default_glob_helper_path_is_none() -> None:
    assert WorkspaceBase._glob_helper_path.fget(object()) is None


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



def test_powershell_tool_encodes_command_and_asks_permission() -> None:
    from Capabilities.tool import PowerShell

    async def _run() -> None:
        backend = AsyncMock()
        backend.exec_shell.side_effect = [
            ExecResult(0, b"", b""),
            ExecResult(0, b"ok\r\n", b""),
        ]
        tool = PowerShell(cwd="workspace", backend=backend)

        decision = await tool.check_permissions({}, None)
        assert decision.behavior == PermissionBehavior.ASK
        assert await tool.generate_suggestions({}) == []

        chunks = [
            chunk
            async for chunk in await tool(
                command="Write-Output 'ok'",
                description="test command",
                timeout=700000,
            )
        ]

        assert chunks[0].content[0].text == "ok\n"
        assert chunks[0].is_last is True
        assert backend.exec_shell.await_args_list[1].kwargs["cwd"] == "workspace"
        assert backend.exec_shell.await_args_list[1].kwargs["timeout"] == 600.0
        argv = backend.exec_shell.await_args_list[1].args[0]
        assert argv[:4] == ["pwsh", "-NoLogo", "-NoProfile", "-NonInteractive"]
        assert "-EncodedCommand" in argv

    asyncio.run(_run())


def test_agent_on_check_permission_middleware_can_deny_before_engine() -> None:
    class _FakeModel:
        model = "fake"
        context_size = 8192

    class _Tool(ToolBase):
        name = "guarded"
        description = "guarded tool"
        input_schema = {"type": "object", "properties": {}, "required": []}
        is_read_only = False
        is_concurrency_safe = True

        async def check_permissions(self, tool_input, context):
            return PermissionDecision(
                behavior=PermissionBehavior.ALLOW,
                message="tool allowed",
            )

        async def call(self):
            return ToolResponse(
                content=[TextBlock(text="should not execute")],
                state=ToolResultState.SUCCESS,
            )

    class _DenyMiddleware(MiddlewareBase):
        async def on_check_permission(self, agent, input_kwargs, next_handler):
            return PermissionDecision(
                behavior=PermissionBehavior.DENY,
                message="blocked by middleware",
            )

    async def _run() -> None:
        tool = _Tool()
        agent = Agent(
            name="agent",
            system_prompt="prompt",
            model=_FakeModel(),
            toolkit=Toolkit(tools=[tool]),
            middlewares=[_DenyMiddleware()],
        )
        engine = AsyncMock(
            return_value=PermissionDecision(
                behavior=PermissionBehavior.ALLOW,
                message="allowed",
            ),
        )
        agent._engine.check_permission = engine

        decision = await agent._check_permission(
            ToolCallBlock(id="call-1", name="guarded", input="{}"),
            tool,
            {},
        )

        assert decision.behavior == PermissionBehavior.DENY
        assert decision.message == "blocked by middleware"
        engine.assert_not_awaited()

    asyncio.run(_run())


def test_workspace_router_exposes_artifact_routes() -> None:
    from Service.app._router import workspace_router

    routes = {(route.path, tuple(sorted(route.methods))) for route in workspace_router.routes}

    assert ("/workspace/files/dir", ("GET",)) in routes
    assert ("/workspace/files", ("GET",)) in routes
    assert ("/workspace/files/token", ("POST",)) in routes


def test_session_router_exposes_status_and_interrupt_routes() -> None:
    from Service.app._router import session_router

    routes = {(route.path, tuple(sorted(route.methods))) for route in session_router.routes}

    assert ("/sessions/{session_id}/status", ("GET",)) in routes
    assert ("/sessions/{session_id}/interrupt", ("POST",)) in routes


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
    def __init__(self) -> None:
        self.locked = False
        self.queued = []

    @asynccontextmanager
    async def acquire_lock(self, key, ttl_secs):
        yield

    async def log_trim(self, key):
        return None

    async def is_locked(self, key):
        return self.locked

    async def queue_push(self, key, payload):
        self.queued.append((key, payload))

    async def publish(self, key, payload):
        self.queued.append((key, payload))


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


def test_v206_optional_extras_keep_legacy_aliases() -> None:
    import tomllib
    from pathlib import Path

    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    extras = data["project"]["optional-dependencies"]

    for key in [
        "storage-redis",
        "storage-sql",
        "storage-s3",
        "channel",
        "workspace-daytona",
        "workspace-k8s",
        "workspace-opensandbox",
        "vdb-milvus",
        "vdb-mongodb",
        "vdb-elasticsearch",
        "memory-reme",
    ]:
        assert key in extras

    assert "storage" in extras
    assert "mem0" in extras
    assert any("redis" in dep for dep in extras["storage"])


def test_agent_interrupt_closes_parked_tool_calls() -> None:
    from Runtime.event import ReplyEndEvent, UserInterruptEvent

    class _Model:
        model = "fake"
        context_size = 8192

    async def _run() -> None:
        agent = Agent(name="agent", system_prompt="prompt", model=_Model())
        agent.state.reply_id = "reply-1"
        agent.state.context.append(
            AssistantMsg(
                id="reply-1",
                name="agent",
                content=[
                    ToolCallBlock(
                        id="call-1",
                        name="external_tool",
                        input="{}",
                        state=ToolCallState.ASKING,
                    ),
                ],
            ),
        )

        items = [
            item
            async for item in agent._reply(
                inputs=UserInterruptEvent(reply_id="reply-1"),
            )
        ]

        tool_results = agent.state.context[-1].get_content_blocks(
            "tool_result",
        )
        assert len(tool_results) == 1
        assert isinstance(tool_results[0], ToolResultBlock)
        assert tool_results[0].id == "call-1"
        assert tool_results[0].state == ToolResultState.INTERRUPTED
        assert agent.state.context[-1].get_content_blocks("tool_call")[
            0
        ].state == ToolCallState.FINISHED
        assert any(isinstance(item, ReplyEndEvent) for item in items)

    asyncio.run(_run())


def test_session_service_interrupt_enqueues_parked_direct_reply() -> None:
    from Runtime.event import EventType
    from Service.app._service import SessionService
    from Service.app.message_bus import MessageBusKeys

    session = SessionRecord(
        user_id="runtime-key",
        agent_id=None,
        runtime_subject_id="dm_subject_01",
        runtime_profile=_direct_profile(subject_id="dm_subject_01"),
        config=SessionConfig(workspace_id="workspace-01"),
    )
    session.state.context.append(
        AssistantMsg(
            id="reply-1",
            name="DirectModel",
            content=[
                ToolCallBlock(
                    id="call-1",
                    name="external_tool",
                    input="{}",
                    state=ToolCallState.SUBMITTED,
                ),
            ],
        ),
    )
    storage = _FakeStorage(session)
    bus = _FakeMessageBus()

    async def _run() -> None:
        service = SessionService(
            storage=storage,
            message_bus=bus,
            workspace_manager=object(),
        )
        await service.interrupt_session_run(
            "runtime-key",
            session.id,
            runtime_subject_id="dm_subject_01",
        )

    asyncio.run(_run())

    queue_payloads = [
        payload
        for key, payload in bus.queued
        if key == MessageBusKeys.wakeup_queue()
    ]
    assert len(queue_payloads) == 1
    assert queue_payloads[0]["kind"] == MessageBusKeys.WAKEUP_KIND_RESUME
    assert queue_payloads[0]["runtime_subject_id"] == "dm_subject_01"
    assert queue_payloads[0]["input"]["type"] == EventType.USER_INTERRUPT
    assert queue_payloads[0]["input"]["reply_id"] == "reply-1"


def test_runtime_injection_config_is_disabled_by_default() -> None:
    from Runtime.agent import InjectionConfig, ReActConfig

    assert ReActConfig().structured_output_grace_iters == 5
    assert InjectionConfig().inject_runtime_state is False


def test_runtime_injection_adds_hint_only_when_enabled() -> None:
    from Runtime.agent import InjectionConfig
    from Runtime.message import HintBlock

    class _Model:
        model = "fake"
        context_size = 8192

    async def _run() -> None:
        agent = Agent(
            name="agent",
            system_prompt="prompt",
            model=_Model(),
            injection_config=InjectionConfig(
                inject_runtime_state=True,
                timezone="UTC",
                extra_fields={"environment": "ASOFT"},
            ),
        )
        prepared = await agent._prepare_model_input()
        hint_messages = [
            msg
            for msg in prepared["messages"]
            if any(isinstance(block, HintBlock) for block in msg.content)
        ]

        assert hint_messages
        hint_block = hint_messages[-1].get_content_blocks("hint")[0]
        assert "<current-time>" in hint_block.hint
        assert "<timezone>UTC</timezone>" in hint_block.hint
        assert "<environment>ASOFT</environment>" in hint_block.hint
        assert agent.state.context == []

    asyncio.run(_run())


def test_agent_reply_can_attach_structured_output() -> None:
    from Runtime.message import UserMsg

    class _Answer(BaseModel):
        ok: bool
        summary: str

    class _Model:
        model = "fake"
        context_size = 8192

        async def __call__(self, **kwargs):
            return ChatResponse(
                content=[TextBlock(text="done")],
                is_last=True,
            )

        async def generate_structured_output(self, messages, structured_model):
            return SimpleNamespace(content={"ok": True, "summary": "done"})

        async def count_tokens(self, **kwargs):
            return 1

    async def _run() -> None:
        agent = Agent(name="agent", system_prompt="prompt", model=_Model())
        msg = await agent.reply(
            UserMsg("user", "hello"),
            structured_schema=_Answer,
        )

        assert msg.structured_output == {"ok": True, "summary": "done"}
        assert agent.state.context[-1].structured_output == msg.structured_output

    asyncio.run(_run())
