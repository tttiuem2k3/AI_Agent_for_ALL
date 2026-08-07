# -*- coding: utf-8 -*-
"""Schema-driven ERPX tools backed by the curated SERVICES Tool Gateway."""
from collections.abc import Awaitable, Callable
from typing import Any

from Runtime.message import TextBlock, ToolResultState
from Capabilities.permission import (
    PermissionBehavior,
    PermissionContext,
    PermissionDecision,
    PermissionMode,
)

from ._base import ToolBase
from ._response import ToolChunk


ERPXExecute = Callable[
    [
        str, str, str, str, str, str | None, str | None,
        str, str, str, dict[str, Any],
    ],
    Awaitable[dict[str, Any]],
]


class ERPXExternalTool(ToolBase):
    """A Tool whose execution belongs to ON, exposed to the model only.

    Same model-facing surface as :class:`ERPXDynamicTool` — same name, same
    description, same schema — and the opposite execution contract:
    ``is_external_tool = True`` makes AgentScope mark the call ``SUBMITTED``,
    emit ``RequireExternalExecutionEvent`` and return from its loop.  ON then
    decides whether the call runs now, waits for a reviewer, or is rejected,
    and resumes the turn with an ``ExternalExecutionResultEvent``.

    That ordering is the whole point.  With the in-process wrapper, a Tool
    requiring approval called back into the Tool Gateway *before* the approval
    row existed; the gateway found nothing to match and failed the turn, and the
    user's later approval had no turn left to resume.

    ``check_permissions`` deliberately always allows: approval is ON's decision,
    made against its own ledger, and duplicating it here as a second HITL gate
    would stop the turn locally for a call the runtime is not going to make.
    """

    is_concurrency_safe = False
    is_external_tool = True
    is_state_injected = False
    is_tool_call_id_injected = True
    is_mcp = False
    mcp_name = None

    def __init__(
        self,
        *,
        tool_id: str,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        output_schema: dict[str, Any] | None,
        is_read_only: bool,
        require_approval: bool,
    ) -> None:
        super().__init__()
        self.tool_id = tool_id
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.output_schema = output_schema
        self.is_read_only = is_read_only
        self.require_approval = require_approval

    async def check_permissions(
        self,
        tool_input: dict[str, Any],
        context: PermissionContext,
    ) -> PermissionDecision:
        """Allow locally; the real gate is ON's invocation ledger."""
        del tool_input, context
        return PermissionDecision(
            behavior=PermissionBehavior.ALLOW,
            message=(
                f"ERPX operation '{self.name}' is executed by ON, "
                "not by the runtime."
            ),
        )

    async def call(self, **arguments: Any) -> ToolChunk:
        """Never reachable — raise loudly rather than execute in-process."""
        del arguments
        raise RuntimeError(
            f"ERPX external Tool '{self.name}' must be executed by ON. "
            "Reaching this call means the runtime ignored is_external_tool, "
            "which would run the operation before ON approved it.",
        )


class ERPXDynamicTool(ToolBase):
    """One model-visible function bound to a hidden ERPX ``ToolID``."""

    is_concurrency_safe = False
    is_external_tool = False
    is_state_injected = False
    is_tool_call_id_injected = True
    is_mcp = False
    mcp_name = None

    def __init__(
        self,
        *,
        tool_id: str,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        output_schema: dict[str, Any] | None,
        is_read_only: bool,
        require_approval: bool,
        user_id: str,
        division_id: str,
        execution_mode: str,
        runtime_subject_id: str | None,
        agent_apk: str | None,
        session_id: str,
        run_id: str,
        capability_hash: str,
        execute: ERPXExecute,
    ) -> None:
        super().__init__()
        if not is_read_only and not require_approval:
            raise ValueError("Writable ERPX tools must require approval.")
        if not run_id:
            raise ValueError("ERPXDynamicTool requires a trusted RunID.")

        self.tool_id = tool_id
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.output_schema = output_schema
        self.is_read_only = is_read_only
        self.require_approval = require_approval
        self._user_id = user_id
        self._division_id = division_id
        self._execution_mode = execution_mode
        self._runtime_subject_id = runtime_subject_id
        self._agent_apk = agent_apk
        self._session_id = session_id
        self._run_id = run_id
        self._capability_hash = capability_hash
        self._execute = execute

    async def check_permissions(
        self,
        tool_input: dict[str, Any],
        context: PermissionContext,
    ) -> PermissionDecision:
        """Map catalog approval policy onto the existing HITL engine."""
        del tool_input
        if self.require_approval:
            if context.mode == PermissionMode.BYPASS:
                return PermissionDecision(
                    behavior=PermissionBehavior.DENY,
                    message=(
                        "Writable ERPX operations cannot execute in "
                        "bypass mode."
                    ),
                )
            return PermissionDecision(
                behavior=PermissionBehavior.ASK,
                message=f"ERPX operation '{self.name}' requires approval.",
                bypass_immune=True,
            )
        return PermissionDecision(
            behavior=PermissionBehavior.ALLOW,
            message=f"Read-only ERPX operation '{self.name}' is allowed.",
        )

    async def call(
        self,
        *,
        _runtime_tool_call_id: str,
        **arguments: Any,
    ) -> ToolChunk:
        """Execute using only hidden trusted context plus schema arguments."""
        result = await self._execute(
            self.tool_id,
            _runtime_tool_call_id,
            self._run_id,
            self._session_id,
            self._execution_mode,
            self._runtime_subject_id,
            self._agent_apk,
            self._user_id,
            self._division_id,
            self._capability_hash,
            arguments,
        )
        message = str(result.get("message") or "ERPX operation completed.")
        return ToolChunk(
            content=[TextBlock(text=message)],
            state=ToolResultState.SUCCESS,
            metadata={
                "tool_id": self.tool_id,
                "execution_id": result.get("execution_id"),
                "data": result.get("data"),
            },
        )
