# -*- coding: utf-8 -*-
# pylint: disable=protected-access
"""Tests for :func:`get_toolkit` — the single entry point that assembles
the per-chat-turn :class:`Toolkit` from every tool source the framework
manages.

Verifies the assembly rules:

- workspace builtins are always included;
- the four ``Task*`` planning tools are always included;
- :class:`ToolStop` (from ``BackgroundTaskManager``) is always included;
- the four ``Schedule*`` tools only when ``session.config.chat_model_config``
  is set (they need a model to fire new runs with);
- team tools are role-gated by ``agent_record.source``: ``"team"`` →
  one ``TeamSay`` (worker variant); anything else → the full
  leader-side toolset of four;
- caller-supplied ``extra_factory`` results land at the end.
"""
import hashlib
from pathlib import Path
from typing import Any
from unittest import IsolatedAsyncioTestCase

import frontmatter

from Runtime.agent import ContextConfig, ReActConfig
from Service.app import (
    BackgroundTaskManager,
    SchedulerManager,
)
from Service.app._service import get_toolkit
from Service.app.storage import (
    AgentData,
    AgentRecord,
    CapabilityManifest,
    ChatModelConfig,
    SessionConfig,
    SessionRecord,
    SkillCapability,
    ToolCapability,
)
from Capabilities.skill import Skill
from Capabilities.tool import ToolBase


class _FakeWorkspace:
    """Stand-in for a resolved :class:`WorkspaceBase` — only the three
    methods :func:`get_toolkit` calls are implemented."""

    def __init__(
        self,
        tools: list[ToolBase] | None = None,
        skills: list | None = None,
        mcps: list | None = None,
    ) -> None:
        self._tools = tools or []
        self._skills = skills or []
        self._mcps = mcps or []

    async def list_tools(self) -> list[ToolBase]:
        """Return the configured workspace tools."""
        return list(self._tools)

    async def list_skills(self) -> list:
        """Return the configured workspace skills."""
        return list(self._skills)

    async def list_mcps(self) -> list:
        """Return the configured workspace MCP descriptors."""
        return list(self._mcps)

    async def remove_skill(self, skill_name: str) -> None:
        """Remove one skill by its agent-facing name."""
        self._skills = [
            skill for skill in self._skills if skill.name != skill_name
        ]

    async def add_skill(self, skill_path: str) -> None:
        """Load a canonical SKILL.md from the temporary source directory."""
        path = Path(skill_path) / "SKILL.md"
        content = frontmatter.loads(path.read_text(encoding="utf-8"))
        self._skills.append(
            Skill(
                name=str(content["name"]),
                description=str(content["description"]),
                dir=skill_path,
                markdown=content.content,
                updated_at=0,
            ),
        )


class _NullBus:
    """``MessageBus`` placeholder. Team tools only carry the reference;
    nothing in :func:`get_toolkit` actually awaits it."""


def _make_agent(
    *,
    source: str = "user",
    name: str = "A",
    base_capabilities: CapabilityManifest | None = None,
) -> AgentRecord:
    """Build a minimal :class:`AgentRecord`."""
    return AgentRecord(
        user_id="u",
        source=source,
        data=AgentData(
            name=name,
            system_prompt=f"You are {name}.",
            context_config=ContextConfig(),
            react_config=ReActConfig(),
            base_capabilities=base_capabilities,
        ),
    )


def _make_session(
    *,
    user_id: str,
    agent_id: str,
    with_model: bool,
    effective_capabilities: CapabilityManifest | None = None,
) -> SessionRecord:
    """Build a minimal :class:`SessionRecord`, optionally with a chat
    model config."""
    cfg = SessionConfig(
        workspace_id="ws",
        chat_model_config=(
            ChatModelConfig(
                type="dashscope_credential",
                credential_id="c",
                model="m",
                parameters={},
            )
            if with_model
            else None
        ),
        effective_capabilities=effective_capabilities,
    )
    return SessionRecord(user_id=user_id, agent_id=agent_id, config=cfg)


class _NoOpStorage:
    """Storage placeholder. ``get_toolkit`` itself does not call any
    storage method — the team tools bind a reference for later use."""


def _tool_names(toolkit: Any) -> list[str]:
    """Extract every registered tool name from a :class:`Toolkit`,
    walking its tool groups."""
    return [t.name for group in toolkit.tool_groups for t in group.tools]


class _StubTool(ToolBase):
    """Minimal :class:`ToolBase` subclass that satisfies the abstract
    methods so :func:`get_toolkit` can register the instance.

    Sub-classes override ``name`` and ``description``; nothing in the
    tests actually calls the tool, so the implementations are no-ops.
    """

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
        """No-op permission check — the tests do not exercise it."""

    async def __call__(self, *args: Any, **kwargs: Any) -> None:
        """No-op invocation — the tests never execute the tool."""


class TestErpxCapabilityFiltering(IsolatedAsyncioTestCase):
    """Explicit ERPX manifests filter assignable tools fail-closed."""

    async def test_filters_workspace_and_extra_tools(self) -> None:
        """Only manifest-selected assignable tools reach the Toolkit."""
        read_capability = ToolCapability(
            tool_id="ASCOPE_READ",
            function_name="Read",
            tool_type="Builtin",
            tool_group="Workspace",
            description_for_llm="Read a file.",
            input_schema={"type": "object", "properties": {}},
            is_read_only=True,
            require_approval=True,
        )
        api_capability = ToolCapability(
            tool_id="API_READ",
            function_name="read_api",
            tool_type="ServicesApi",
            tool_group="ERPX",
            description_for_llm="Read ERPX data.",
            input_schema={"type": "object", "properties": {}},
            is_read_only=True,
            require_approval=False,
        )
        base = CapabilityManifest(
            agent_apk="agent-apk",
            agent_id="AGENT",
            division_id="D1",
            capability_hash="a" * 64,
            tools=[read_capability, api_capability],
        )
        effective = CapabilityManifest(
            agent_apk="agent-apk",
            agent_id="AGENT",
            user_id="u",
            division_id="D1",
            capability_hash="b" * 64,
            tools=[read_capability, api_capability],
        )
        agent = _make_agent(base_capabilities=base)
        session = _make_session(
            user_id="erpx:customer:D1:runtime",
            agent_id=agent.id,
            with_model=False,
            effective_capabilities=effective,
        )

        class _Read(_StubTool):
            name = "Read"

        class _Write(_StubTool):
            name = "Write"

        class _ReadApi(_StubTool):
            name = "read_api"

        class _UnassignedApi(_StubTool):
            name = "unassigned_api"

        async def extras(*_args: Any) -> list[ToolBase]:
            return [_ReadApi(), _UnassignedApi()]

        toolkit = await get_toolkit(
            storage=_NoOpStorage(),  # type: ignore[arg-type]
            workspace=_FakeWorkspace(  # type: ignore[arg-type]
                tools=[_Read(), _Write()],
                mcps=[object()],
            ),
            scheduler_manager=SchedulerManager(
                storage=_NoOpStorage(),  # type: ignore[arg-type]
                message_bus=_NullBus(),  # type: ignore[arg-type]
            ),
            background_task_manager=BackgroundTaskManager(
                message_bus=_NullBus(),  # type: ignore[arg-type]
            ),
            message_bus=_NullBus(),  # type: ignore[arg-type]
            user_id="erpx:customer:D1:runtime",
            agent_record=agent,
            session_record=session,
            extra_factory=extras,
        )

        names = _tool_names(toolkit)
        self.assertIn("Read", names)
        self.assertIn("read_api", names)
        self.assertNotIn("Write", names)
        self.assertNotIn("unassigned_api", names)
        self.assertEqual(toolkit.tool_groups[0].mcps, [])
        self.assertIn("TaskCreate", names)

    async def test_only_effective_skills_are_model_visible(self) -> None:
        """Assigned Skill content is materialized without exposing extras."""
        markdown = (
            "---\n"
            'name: "sales-guide"\n'
            'description: "Use the assigned sales flow."\n'
            "---\n\n"
            "Follow the approved sales-order steps.\n"
        )
        capability = SkillCapability(
            skill_id="sales-guide",
            description="Use the assigned sales flow.",
            skill_markdown=markdown,
            content_hash=hashlib.sha256(
                markdown.encode("utf-8"),
            ).hexdigest(),
        )
        base = CapabilityManifest(
            agent_apk="agent-apk",
            agent_id="AGENT",
            division_id="D1",
            capability_hash="a" * 64,
            skills=[capability],
        )
        effective = CapabilityManifest(
            agent_apk="agent-apk",
            agent_id="AGENT",
            user_id="u",
            division_id="D1",
            capability_hash="b" * 64,
            skills=[capability],
        )
        agent = _make_agent(base_capabilities=base)
        session = _make_session(
            user_id="u",
            agent_id=agent.id,
            with_model=False,
            effective_capabilities=effective,
        )
        workspace = _FakeWorkspace(
            skills=[
                Skill(
                    name="unassigned-guide",
                    description="Must stay hidden.",
                    dir="manual",
                    markdown="Unassigned instructions.",
                    updated_at=0,
                ),
            ],
        )

        toolkit = await get_toolkit(
            storage=_NoOpStorage(),  # type: ignore[arg-type]
            workspace=workspace,  # type: ignore[arg-type]
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

        instructions = await toolkit.get_skill_instructions()
        self.assertIn("sales-guide", instructions)
        self.assertNotIn("unassigned-guide", instructions)
        self.assertEqual(
            {skill.name for skill in workspace._skills},
            {"sales-guide", "unassigned-guide"},
        )


class TestGetToolkitBaseAssembly(IsolatedAsyncioTestCase):
    """User-owned agent (``source="user"``) gets the full set."""

    async def test_user_agent_gets_all_sources(self) -> None:
        """A user-owned agent receives workspace, planning, scheduling,
        ToolStop, and the four leader-side team tools."""
        agent = _make_agent(source="user")
        session = _make_session(
            user_id="u",
            agent_id=agent.id,
            with_model=True,
        )

        class _WsTool(_StubTool):
            """Stub workspace tool registered through ``_FakeWorkspace``."""

            name: str = "ws-bash"
            description: str = "stub workspace tool"

        ws_tool = _WsTool()
        workspace = _FakeWorkspace(tools=[ws_tool])

        toolkit = await get_toolkit(
            storage=_NoOpStorage(),  # type: ignore[arg-type]
            workspace=workspace,  # type: ignore[arg-type]
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
            extra_factory=None,
        )

        names = set(_tool_names(toolkit))
        # Workspace tool present.
        self.assertIn("ws-bash", names)
        # Planning tools present.
        self.assertTrue(
            {"TaskCreate", "TaskList", "TaskGet", "TaskUpdate"} <= names,
        )
        # Background task control present.
        self.assertIn("ToolStop", names)
        # Schedule control present (model_config is set).
        self.assertTrue(
            {
                "ScheduleCreate",
                "ScheduleView",
                "ScheduleDelete",
                "ScheduleList",
            }
            <= names,
        )
        # Leader-side team tools (4 of them).
        self.assertTrue(
            {"TeamCreate", "AgentCreate", "TeamSay", "TeamDelete"} <= names,
        )


class TestGetToolkitWorkerVariant(IsolatedAsyncioTestCase):
    """Worker agent (``source="team"``) only gets ``TeamSay``."""

    async def test_worker_only_gets_team_say(self) -> None:
        """A worker agent (``source="team"``) receives only ``TeamSay``
        from the team toolset."""
        agent = _make_agent(source="team", name="worker")
        session = _make_session(
            user_id="u",
            agent_id=agent.id,
            with_model=True,
        )
        toolkit = await get_toolkit(
            storage=_NoOpStorage(),  # type: ignore[arg-type]
            workspace=_FakeWorkspace(),  # type: ignore[arg-type]
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
            extra_factory=None,
        )
        names = set(_tool_names(toolkit))
        # Only TeamSay from the team toolset.
        self.assertIn("TeamSay", names)
        for missing in ("TeamCreate", "AgentCreate", "TeamDelete"):
            self.assertNotIn(missing, names)


class TestGetToolkitSchedulingGuard(IsolatedAsyncioTestCase):
    """``Schedule*`` tools are only attached when the session has a
    model configured."""

    async def test_no_schedule_tools_without_model_config(self) -> None:
        """Without a ``chat_model_config`` on the session, the four
        ``Schedule*`` tools are omitted from the toolkit."""
        agent = _make_agent(source="user")
        session = _make_session(
            user_id="u",
            agent_id=agent.id,
            with_model=False,
        )
        toolkit = await get_toolkit(
            storage=_NoOpStorage(),  # type: ignore[arg-type]
            workspace=_FakeWorkspace(),  # type: ignore[arg-type]
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
            extra_factory=None,
        )
        names = set(_tool_names(toolkit))
        for missing in (
            "ScheduleCreate",
            "ScheduleView",
            "ScheduleDelete",
            "ScheduleList",
        ):
            self.assertNotIn(missing, names)


class TestGetToolkitExtraFactory(IsolatedAsyncioTestCase):
    """Tools returned by ``extra_factory`` end up in the final toolkit."""

    async def test_extra_factory_tools_are_attached(self) -> None:
        """Tools returned by ``extra_factory`` end up in the final
        toolkit alongside the framework-builtin ones."""

        class _ExtraTool(_StubTool):
            """Stub tool emitted by the ``extra_factory`` callback."""

            name: str = "my-extra"
            description: str = "stub extra tool"

        extra_tool = _ExtraTool()

        async def factory(
            _user_id: str,
            _agent_id: str,
            _session_id: str,
        ) -> list[ToolBase]:
            """Stub extra-factory that always returns ``extra_tool``."""
            return [extra_tool]

        agent = _make_agent()
        session = _make_session(
            user_id="u",
            agent_id=agent.id,
            with_model=True,
        )
        toolkit = await get_toolkit(
            storage=_NoOpStorage(),  # type: ignore[arg-type]
            workspace=_FakeWorkspace(),  # type: ignore[arg-type]
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
            extra_factory=factory,
        )
        self.assertIn("my-extra", _tool_names(toolkit))
