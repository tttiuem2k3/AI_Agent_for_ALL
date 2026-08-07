# -*- coding: utf-8 -*-
"""Task 3.1 — the Workflow runtime profile is a closed world.

A workflow Agent node runs unattended: nobody is watching the turn, and the
graph author picked exactly which Tools the node may use.  Every tool the
framework attaches unconditionally today — the ``Task*`` planners, the
background ``ToolStop`` control, the schedule group, the team tools, the
workspace MCPs — is therefore wrong for a workflow turn.  Leaving them
attached is not merely untidy: an unattended model that reaches for
``ToolStop`` or ``TeamCreate`` takes an action nobody authorised, and that is
exactly what was observed on the dev box (the model called ``ToolStop`` with
``task_id = "ON_CHAT_LIST_CONVERSATIONS"``).

The assertion below is deliberately an equality, not a subset: the toolkit's
tool names must be *exactly* the manifest's ``function_name`` set.
"""
from typing import Any
from unittest import IsolatedAsyncioTestCase

from Runtime.agent import ContextConfig, ReActConfig
from Service.app import BackgroundTaskManager, SchedulerManager
from Service.app._service import get_toolkit
from Service.app.storage import (
    AgentData,
    AgentRecord,
    CapabilityManifest,
    ChatModelConfig,
    SessionConfig,
    SessionRecord,
    ToolCapability,
    WorkflowRuntimeProfile,
)
from Capabilities.tool import ToolBase


class _FakeWorkspace:
    """Only the three discovery methods :func:`get_toolkit` calls."""

    def __init__(self, tools: list[ToolBase], mcps: list | None = None) -> None:
        self._tools = tools
        self._mcps = mcps or []

    async def list_tools(self) -> list[ToolBase]:
        return list(self._tools)

    async def list_skills(self) -> list:
        return []

    async def list_mcps(self) -> list:
        return list(self._mcps)


class _NullBus:
    """``MessageBus`` placeholder — nothing here awaits it."""


class _NoOpStorage:
    """Storage placeholder — ``get_toolkit`` itself calls nothing on it."""


class _StubTool(ToolBase):
    name: str = "stub"
    description: str = "stub tool"
    input_schema: dict = {}
    is_concurrency_safe: bool = True
    is_read_only: bool = False
    is_state_injected: bool = False
    is_external_tool: bool = False
    is_mcp: bool = False
    mcp_name: str | None = None

    async def check_permissions(self, *args: Any, **kwargs: Any) -> None:
        """No-op — never exercised here."""

    async def __call__(self, *args: Any, **kwargs: Any) -> None:
        """No-op — never executed here."""


class _Read(_StubTool):
    name = "Read"


class _Write(_StubTool):
    name = "Write"


def _capability(function_name: str, tool_id: str) -> ToolCapability:
    return ToolCapability(
        tool_id=tool_id,
        function_name=function_name,
        tool_type="Builtin",
        tool_group="Workspace",
        description_for_llm=f"{function_name} something.",
        input_schema={"type": "object", "properties": {}},
        is_read_only=True,
        require_approval=False,
    )


def _manifest(user_id: str | None = None) -> CapabilityManifest:
    return CapabilityManifest(
        agent_apk="agent-apk",
        agent_id="AGENT",
        user_id=user_id,
        division_id="D1",
        capability_hash="a" * 64,
        tools=[_capability("Read", "ASCOPE_READ")],
    )


def _tool_names(toolkit: Any) -> set[str]:
    return {
        tool.name
        for group in toolkit.tool_groups
        for tool in group.tools
    }


class ERPXWorkflowProfileTest(IsolatedAsyncioTestCase):
    async def _assemble(self, *, workflow: bool):
        agent = AgentRecord(
            user_id="u",
            source="user",
            data=AgentData(
                name="A",
                system_prompt="You are A.",
                context_config=ContextConfig(),
                react_config=ReActConfig(),
                base_capabilities=_manifest(),
            ),
        )
        session = SessionRecord(
            user_id="erpx:customer:D1:runtime",
            agent_id=agent.id,
            # Có model config để nhánh schedule đủ điều kiện gắn — nếu không,
            # test "không có schedule tool" sẽ xanh vì lý do sai.
            config=SessionConfig(
                workspace_id="ws",
                chat_model_config=ChatModelConfig(
                    type="dashscope_credential",
                    credential_id="c",
                    model="m",
                    parameters={},
                ),
                effective_capabilities=_manifest(user_id="u"),
            ),
            runtime_profile=(
                WorkflowRuntimeProfile(agent_id=agent.id) if workflow else None
            ),
        )
        return await get_toolkit(
            storage=_NoOpStorage(),
            workspace=_FakeWorkspace([_Read(), _Write()], mcps=["mcp-1"]),
            scheduler_manager=SchedulerManager(
                storage=_NoOpStorage(),  # type: ignore[arg-type]
                message_bus=_NullBus(),  # type: ignore[arg-type]
            ),
            background_task_manager=BackgroundTaskManager(
                message_bus=_NullBus(),  # type: ignore[arg-type]
            ),
            message_bus=_NullBus(),  # type: ignore[arg-type]
            user_id="u",
            agent_record=agent,
            session_record=session,
        )

    async def test_workflow_profile_attaches_only_manifest_tools(self) -> None:
        toolkit = await self._assemble(workflow=True)

        # Bằng đúng tập function_name của manifest, không phải tập con của nó:
        # mọi thứ framework tự gắn thêm đều phải biến mất.
        self.assertEqual(_tool_names(toolkit), {"Read"})

    async def test_agent_profile_keeps_every_framework_tool(self) -> None:
        """Đối chứng: cùng dàn dựng, chỉ khác profile.

        Nếu test này cũng chỉ thấy {'Read'} thì test trên xanh vì lý do sai
        (bộ lọc manifest, không phải profile) — nên nó phải thấy nhiều hơn.
        """
        toolkit = await self._assemble(workflow=False)
        names = _tool_names(toolkit)

        self.assertIn("Read", names)
        self.assertIn("TaskCreate", names)
        self.assertIn("TeamCreate", names)
        self.assertTrue(any(name.startswith("Schedule") for name in names))
