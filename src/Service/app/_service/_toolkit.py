# -*- coding: utf-8 -*-
"""Toolkit assembly for an (agent, session) pair.

The single entry point :func:`get_toolkit` gathers every tool source —
workspace builtins, MCPs, skills, planning tools (Task*), background-task
control (ToolStop), schedule control (Schedule*), team participation
tools, and caller-supplied extras — into one :class:`Toolkit`.
"""
from pathlib import Path
import tempfile
from typing import Any

import frontmatter

from .._manager import BackgroundTaskManager, SchedulerManager
from ..message_bus import MessageBus
from .._tool import AgentCreate, TeamCreate, TeamDelete, TeamSay
from .._types import AgentToolFactory, SubAgentTemplate
from ..storage import (
    AgentRecord,
    CapabilityManifest,
    CapabilityManifestV2,
    DirectModelRuntimeProfile,
    SessionRecord,
    SkillCapability,
    StorageBase,
)
from Capabilities.tool import (
    TaskCreate,
    TaskGet,
    TaskList,
    TaskUpdate,
    Toolkit,
    ToolGroup,
)
from Capabilities.workspace import WorkspaceBase


def _effective_tool_names(
    *,
    user_id: str,
    agent_record: AgentRecord | None,
    session_record: SessionRecord,
    tool_type: str,
) -> set[str] | None:
    """Return allowed names for an ERPX manifest, or ``None`` for legacy."""
    effective = session_record.config.effective_capabilities
    if effective is None:
        return None

    profile = session_record.runtime_profile
    if isinstance(profile, DirectModelRuntimeProfile):
        if not isinstance(effective, CapabilityManifestV2):
            raise ValueError(
                "DirectModel runtime requires capability manifest v2.",
            )
        base = profile.base_capabilities
        if (
            effective.subject_type != "DirectModel"
            or effective.subject_id != session_record.runtime_subject_id
            or effective.subject_id != base.subject_id
            or effective.user_id != base.user_id
            or effective.division_id != base.division_id
        ):
            raise ValueError(
                "DirectModel capability manifest does not match the session.",
            )
    else:
        if agent_record is None:
            raise ValueError("Agent runtime requires AgentRecord.")
        if not isinstance(effective, CapabilityManifest):
            raise ValueError("Agent runtime requires capability manifest v1.")
        base = agent_record.data.base_capabilities
        if base is None:
            raise ValueError(
                "ERPX effective capabilities require Agent base capabilities.",
            )
    # ``user_id`` is the authenticated runtime namespace (ERPX RuntimeKey),
    # not the ERP application UserID stored in the capability manifest.
    # The chat router locks that ERP UserID to the session's initial binding.
    if isinstance(effective, CapabilityManifest) and (
        effective.agent_apk != base.agent_apk
        or effective.agent_id != base.agent_id
        or effective.division_id != base.division_id
    ):
        raise ValueError(
            "ERPX effective capability manifest does not match the Agent/session.",
        )

    base_tools = {tool.tool_id: tool for tool in base.tools}
    for effective_tool in effective.tools:
        base_tool = base_tools.get(effective_tool.tool_id)
        if (
            base_tool is None
            or effective_tool.model_dump(mode="json")
            != base_tool.model_dump(mode="json")
        ):
            raise ValueError(
                "ERPX effective capabilities are not a subset of Agent "
                "base capabilities.",
            )

    base_skills = {skill.skill_id: skill for skill in base.skills}
    for effective_skill in effective.skills:
        base_skill = base_skills.get(effective_skill.skill_id)
        if (
            base_skill is None
            or effective_skill.model_dump(mode="json")
            != base_skill.model_dump(mode="json")
        ):
            raise ValueError(
                "ERPX effective Skills are not a subset of Agent "
                "base capabilities.",
            )

    return {
        tool.function_name
        for tool in effective.tools
        if tool.tool_type == tool_type
    }


async def _sync_erpx_skills(
    workspace: WorkspaceBase,
    skills: list[SkillCapability],
) -> list:
    """Materialize only effective catalog Skills into the Agent workspace."""
    if not skills:
        return []

    existing = await workspace.list_skills()
    existing_by_name = {skill.name: skill for skill in existing}
    for skill in skills:
        expected_markdown = frontmatter.loads(skill.skill_markdown).content
        current = existing_by_name.get(skill.skill_id)
        if (
            current is not None
            and current.markdown == expected_markdown
            and current.description == skill.description
        ):
            continue
        if current is not None:
            await workspace.remove_skill(skill.skill_id)

        with tempfile.TemporaryDirectory(prefix="erpx-skill-") as temp_dir:
            source_dir = Path(temp_dir) / skill.skill_id
            source_dir.mkdir()
            (source_dir / "SKILL.md").write_text(
                skill.skill_markdown,
                encoding="utf-8",
                newline="\n",
            )
            await workspace.add_skill(str(source_dir))

    effective_by_name = {skill.skill_id: skill for skill in skills}
    materialized = await workspace.list_skills()
    result = []
    for skill in materialized:
        expected = effective_by_name.get(skill.name)
        if expected is None:
            continue
        expected_markdown = frontmatter.loads(
            expected.skill_markdown,
        ).content
        if (
            skill.markdown == expected_markdown
            and skill.description == expected.description
        ):
            result.append(skill)
    if len(result) != len(skills):
        raise ValueError("Not all effective ERPX Skills were materialized.")
    return result


async def get_toolkit(
    *,
    storage: StorageBase,
    workspace: WorkspaceBase,
    scheduler_manager: SchedulerManager,
    background_task_manager: BackgroundTaskManager,
    message_bus: MessageBus,
    user_id: str,
    agent_record: AgentRecord | None,
    session_record: SessionRecord,
    extra_factory: AgentToolFactory | None = None,
    sub_agent_templates: dict[str, SubAgentTemplate] | None = None,
) -> Toolkit:
    """Assemble the complete :class:`Toolkit` for one chat turn.

    Tool sources (in attachment order):

    1. Workspace builtins (Bash / Read / Write / Grep / …)
    2. Planning tools (:class:`TaskCreate` / :class:`TaskList` /
       :class:`TaskGet` / :class:`TaskUpdate`)
    3. Background-task control (:class:`ToolStop`, from
       :meth:`BackgroundTaskManager.list_tools`)
    4. Schedule control (:class:`ScheduleCreate` / :class:`ScheduleView`
       / :class:`ScheduleDelete` / :class:`ScheduleList`, from
       :meth:`SchedulerManager.list_tools`). Only attached when the
       session has a model configured (Schedule tools need a model to
       fire new chats with).
    5. Team tools — selected inline by ``agent_record.source``:
       worker (``"team"``) gets only ``TeamSay``; everyone else gets
       the full leader-side toolset
       (``TeamCreate / AgentCreate / TeamSay / TeamDelete``)
    6. Caller-supplied extras (``extra_factory``)

    Plus the workspace's skills and MCPs, which become the toolkit's
    ``skills_or_loaders`` and ``mcps`` parameters.

    Args:
        storage (`StorageBase`):
            app storage backend; needed by team tools to read
            fresh team / session state at call time, and by schedule
            tools.
        workspace (`WorkspaceBase`):
            Pre-resolved per-session workspace (caller resolves it
            via :meth:`WorkspaceManagerBase.get_workspace`). Used here
            for tool / skill / MCP discovery.
        scheduler_manager (`SchedulerManager`):
            app scheduler. Provides the four schedule tools and
            persists schedules through it.
        background_task_manager (`BackgroundTaskManager`):
            app background-task registry. Provides the
            :class:`ToolStop` tool bound to its live task dict.
        message_bus (`MessageBus`):
            app message bus; passed to team tools so they can
            push HintBlocks + wakeups when delivering inter-session
            messages.
        user_id (`str`):
            Caller user id.
        agent_record (`AgentRecord`):
            Pre-loaded agent record (loaded once by the caller). Its
            ``source`` field determines which team tools are attached.
        session_record (`SessionRecord`):
            Pre-loaded session record (loaded once by the caller).
            Used for the schedule-tool model configuration.
        extra_factory (`AgentToolFactory | None`, optional):
            Async factory invoked once per assembly to produce
            user/session-specific extra tools.
        sub_agent_templates (`dict[str, SubAgentTemplate] | None`, \
optional):
            Sub-agent template registry, keyed by template type.
            Passed to the ``AgentCreate`` tool so it can route to
            the appropriate template when a ``subagent_type`` is
            specified by the leader agent.

    Returns:
        `Toolkit`: Fully populated toolkit (tools + skills + MCPs).
    """

    tool_groups = []

    builtin_names = _effective_tool_names(
        user_id=user_id,
        agent_record=agent_record,
        session_record=session_record,
        tool_type="Builtin",
    )

    # The general tools running in the workspace. An explicit ERPX manifest
    # is fail-closed; ``None`` preserves existing non-ERPX behavior.
    workspace_tools = await workspace.list_tools()
    tools = (
        workspace_tools
        if builtin_names is None
        else [tool for tool in workspace_tools if tool.name in builtin_names]
    )

    direct_model = isinstance(
        session_record.runtime_profile,
        DirectModelRuntimeProfile,
    )

    # Planning tools are Agent-mode capabilities. DirectModel MVP only receives
    # explicitly selected catalog tools plus the internal ToolStop control.
    if not direct_model:
        tools += [TaskCreate(), TaskList(), TaskGet(), TaskUpdate()]

    # Background-task control.
    tools += await background_task_manager.list_tools(
        session_id=session_record.id,
    )

    # Schedule control. Requires a model config on this session because
    # ``ScheduleCreate`` records it into new ``ScheduleRecord`` instances.
    if (
        not direct_model
        and session_record.config.chat_model_config is not None
    ):
        assert agent_record is not None
        # Add schedule tools as a tool group
        tool_groups.append(
            ToolGroup(
                name="schedule_tools",
                description=(
                    """Tools for managing cron schedules. A cron schedule is \
a recurring task that fires at a specified time — at that point, a new \
session is created and an agent will be invoked to complete the given task \
autonomously.

## When to Use This Tool Group
- When you need to create a new cron schedule that triggers at a specific \
time or interval"
- When you're asked to list, inspect, stop, or delete existing cron schedules
"""
                ),
                tools=await scheduler_manager.list_tools(
                    user_id=user_id,
                    agent_id=agent_record.id,
                    chat_model_config=session_record.config.chat_model_config,
                ),
            ),
        )

    # Team tools — variant based on ``agent_record.source``. A worker
    # only gets TeamSay (to report back); a user-owned agent always
    # gets the full leader-side toolset. Each tool checks its own
    # preconditions (am I in a team? am I the leader?) at call time
    # against fresh storage, which is why the full set can be attached
    # unconditionally without needing a stale snapshot of team_id.
    if not direct_model:
        assert agent_record is not None
        team_tool_kwargs: dict[str, Any] = {
            "storage": storage,
            "message_bus": message_bus,
            "user_id": user_id,
            "session_id": session_record.id,
            "agent_id": agent_record.id,
        }
        if agent_record.source == "team":
            tools.append(TeamSay(**team_tool_kwargs, role="worker"))
        else:
            tools += [
                TeamCreate(**team_tool_kwargs),
                AgentCreate(
                    **team_tool_kwargs,
                    sub_agent_templates=sub_agent_templates or {},
                ),
                TeamSay(**team_tool_kwargs, role="leader"),
                TeamDelete(**team_tool_kwargs),
            ]

    # Caller-supplied extras.
    if extra_factory is not None:
        extra_tools = await extra_factory(
            user_id,
            None if direct_model else agent_record.id,
            session_record.id,
        )
        if builtin_names is not None:
            effective = session_record.config.effective_capabilities
            assert effective is not None
            extra_names = {
                tool.function_name
                for tool in effective.tools
                if tool.tool_type != "Builtin"
            }
            extra_tools = [
                tool for tool in extra_tools if tool.name in extra_names
            ]
        tools += extra_tools

    # MCP executors are outside the MVP. Explicit ERPX manifests therefore
    # never inherit workspace MCP visibility. Legacy callers remain unchanged.
    mcps = (
        []
        if direct_model or builtin_names is not None
        else await workspace.list_mcps()
    )

    effective = session_record.config.effective_capabilities
    skills = (
        await workspace.list_skills()
        if effective is None
        else await _sync_erpx_skills(workspace, effective.skills)
    )

    return Toolkit(
        tools=tools,
        skills_or_loaders=skills,
        mcps=mcps,
        tool_groups=tool_groups,
    )
