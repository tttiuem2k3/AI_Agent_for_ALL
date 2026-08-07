# -*- coding: utf-8 -*-
"""Task 3.3 — the ON-only Tool execution endpoint for the PythonRuntime plane.

A Tool whose executor plane is ``PythonRuntime`` runs *inside* the runtime: the
workspace owns the implementation and ON only decides whether and when it may
run.  Before this route there was no way for ON to say "run this one now", so
that whole plane existed on paper only.

The route resolves a **source-registered** key against the session's own
capability manifest and nothing else.  It never accepts a URL, a module path or
a callable name, and a key that is not in the manifest is refused rather than
searched for elsewhere — the manifest is the authorisation, so a key outside it
is by definition unauthorised.
"""
from typing import Any
from unittest import IsolatedAsyncioTestCase

from fastapi import FastAPI
from fastapi.testclient import TestClient

from Runtime.message import TextBlock
from Capabilities.tool import ToolBase
from Capabilities.tool._response import ToolChunk
from Service.app.deps import (
    get_background_task_manager,
    get_message_bus,
    get_scheduler_manager,
    get_storage,
    get_workspace_manager,
)
from Service.app import BackgroundTaskManager, SchedulerManager
from Service.app._router import tool_exec_router
from Runtime.agent import ContextConfig, ReActConfig
from Service.app.storage import (
    AgentData,
    AgentRecord,
    CapabilityManifest,
    SessionConfig,
    SessionRecord,
    ToolCapability,
)


class _EchoTool(ToolBase):
    name: str = "read_runtime"
    description: str = "Read something in the workspace."
    input_schema: dict = {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    }
    is_concurrency_safe: bool = True
    is_read_only: bool = True
    is_state_injected: bool = False
    is_external_tool: bool = False
    is_mcp: bool = False
    mcp_name: str | None = None

    async def check_permissions(self, *args: Any, **kwargs: Any) -> None:
        """Allowed — ON already decided."""

    async def call(self, **arguments: Any) -> ToolChunk:
        return ToolChunk(
            content=[TextBlock(text=f"đọc: {arguments.get('query')}")],
        )


class _Workspace:
    def __init__(self, tools: list[ToolBase]) -> None:
        self._tools = tools
        self.workdir = "/tmp/ws"

    async def list_tools(self) -> list[ToolBase]:
        return list(self._tools)

    async def list_skills(self) -> list:
        return []

    async def list_mcps(self) -> list:
        return []


class _WorkspaceManager:
    def __init__(self, workspace: _Workspace) -> None:
        self._workspace = workspace

    async def get_workspace(self, *_args: Any) -> _Workspace:
        return self._workspace


class _Storage:
    def __init__(self, session: SessionRecord | None) -> None:
        self._session = session

    async def get_session(self, *_args: Any) -> SessionRecord | None:
        return self._session

    async def get_agent(self, *_args: Any) -> AgentRecord:
        # Phiên Agent luôn có AgentRecord, và manifest hiệu lực phải là tập con
        # của base capabilities trên record đó — get_toolkit kiểm điều này.
        return AgentRecord(
            user_id="u",
            source="user",
            data=AgentData(
                name="A",
                system_prompt="You are A.",
                context_config=ContextConfig(),
                react_config=ReActConfig(),
                base_capabilities=_manifest(user_id=None),
            ),
        )


class _NullBus:
    """Placeholder — nothing in this path awaits it."""


def _manifest(
    tool_id: str = "ASCOPE_READ",
    user_id: str | None = "ERP_USER",
) -> CapabilityManifest:
    return CapabilityManifest(
        agent_apk="agent-apk",
        agent_id="AGENT",
        user_id=user_id,
        division_id="D1",
        capability_hash="a" * 64,
        tools=[
            ToolCapability(
                tool_id=tool_id,
                function_name="read_runtime",
                tool_type="Builtin",
                tool_group="Workspace",
                description_for_llm="Read something.",
                input_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
                is_read_only=True,
                require_approval=False,
                executor_type="PythonRuntime",
                is_external_execution=False,
            ),
        ],
    )


def _session(manifest: CapabilityManifest | None) -> SessionRecord:
    return SessionRecord(
        user_id="erpx:customer:D1:runtime",
        agent_id="runtime-agent",
        config=SessionConfig(
            workspace_id="workspace",
            runtime_run_id="run",
            effective_capabilities=manifest,
        ),
    )


def _client(session: SessionRecord | None) -> TestClient:
    app = FastAPI()
    app.include_router(tool_exec_router)
    app.dependency_overrides[get_storage] = lambda: _Storage(session)
    app.dependency_overrides[get_workspace_manager] = lambda: _WorkspaceManager(
        _Workspace([_EchoTool()]),
    )
    app.dependency_overrides[get_scheduler_manager] = lambda: SchedulerManager(
        storage=_Storage(session),  # type: ignore[arg-type]
        message_bus=_NullBus(),  # type: ignore[arg-type]
    )
    app.dependency_overrides[get_background_task_manager] = (
        lambda: BackgroundTaskManager(
            message_bus=_NullBus(),  # type: ignore[arg-type]
        )
    )
    app.dependency_overrides[get_message_bus] = lambda: _NullBus()
    return TestClient(app, raise_server_exceptions=False)


def _body(runtime_tool_key: str = "ASCOPE_READ") -> dict:
    return {
        "user_id": "erpx:customer:D1:runtime",
        "agent_id": "runtime-agent",
        "session_id": "session",
        "invocation_id": "inv-1",
        "runtime_tool_key": runtime_tool_key,
        "arguments": {"query": "x"},
    }


class ERPXToolExecRouterTest(IsolatedAsyncioTestCase):
    async def test_manifest_key_executes_and_returns_a_structured_result(
        self,
    ) -> None:
        response = _client(_session(_manifest())).post(
            "/tool-exec/execute",
            json=_body(),
            headers={"X-User-ID": "erpx:customer:D1:runtime"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["invocation_id"], "inv-1")
        self.assertEqual(payload["state"], "success")
        self.assertEqual(payload["output"][0]["text"], "đọc: x")

    async def test_key_outside_the_manifest_is_forbidden(self) -> None:
        response = _client(_session(_manifest())).post(
            "/tool-exec/execute",
            json=_body("SOMETHING_ELSE"),
            headers={"X-User-ID": "erpx:customer:D1:runtime"},
        )

        self.assertEqual(response.status_code, 403)

    async def test_session_without_a_manifest_is_forbidden(self) -> None:
        """Không manifest = không có gì cấp phép — fail closed."""
        response = _client(_session(None)).post(
            "/tool-exec/execute",
            json=_body(),
            headers={"X-User-ID": "erpx:customer:D1:runtime"},
        )

        self.assertEqual(response.status_code, 403)

    async def test_unknown_session_is_not_found(self) -> None:
        response = _client(None).post(
            "/tool-exec/execute",
            json=_body(),
            headers={"X-User-ID": "erpx:customer:D1:runtime"},
        )

        self.assertEqual(response.status_code, 404)

    async def test_missing_caller_identity_is_unauthorized(self) -> None:
        response = _client(_session(_manifest())).post(
            "/tool-exec/execute",
            json=_body(),
        )

        self.assertIn(response.status_code, (401, 422))
