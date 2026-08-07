# -*- coding: utf-8 -*-
"""Tool execution router — ON asks the runtime to run a Tool it owns.

Tools whose executor plane is ``PythonRuntime`` are implemented by the runtime
itself: the workspace owns the code, and ON only decides whether and when the
call may happen.  Without this route that plane could not exist — ON had no way
to say "run this one now", and the only path into the runtime was the model
choosing a tool mid-turn, which is exactly the decision ON needs to take back.

**What makes this safe is what it refuses to accept.**  The request names a
``runtime_tool_key`` and nothing else: no URL, no module path, no class or
callable name.  The key is resolved against the session's own capability
manifest, so a key ON never published is not "not found somewhere else" — it is
unauthorised, and answered 403.
"""
from fastapi import APIRouter, Depends, HTTPException, status

from ..deps import (
    get_background_task_manager,
    get_current_user_id,
    get_message_bus,
    get_scheduler_manager,
    get_storage,
    get_workspace_manager,
)
from ._schema import ToolExecRequest, ToolExecResponse
from .._manager import BackgroundTaskManager, SchedulerManager
from .._service import get_toolkit
from ..message_bus import MessageBus
from ..storage import StorageBase
from ..workspace_manager import WorkspaceManagerBase

tool_exec_router = APIRouter(
    prefix="/tool-exec",
    tags=["tool-exec"],
    responses={404: {"description": "Not found"}},
)


@tool_exec_router.post("/execute", response_model=ToolExecResponse)
async def execute_tool(
    request: ToolExecRequest,
    caller_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    workspace_manager: WorkspaceManagerBase = Depends(get_workspace_manager),
    scheduler_manager: SchedulerManager = Depends(get_scheduler_manager),
    background_task_manager: BackgroundTaskManager = Depends(
        get_background_task_manager,
    ),
    message_bus: MessageBus = Depends(get_message_bus),
) -> ToolExecResponse:
    """Run one manifest-authorised Tool with ON's approved arguments."""
    if caller_id != request.user_id:
        # The body may not widen the authenticated identity.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tool execution user does not match the caller.",
        )

    session = await storage.get_session(
        request.user_id,
        request.agent_id,
        request.session_id,
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Runtime session was not found.",
        )

    manifest = session.config.effective_capabilities
    if manifest is None:
        # No manifest means nothing authorised anything. Fail closed rather
        # than falling back to "whatever the workspace happens to expose".
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session has no capability manifest.",
        )

    capability = next(
        (
            tool
            for tool in manifest.tools
            if tool.tool_id == request.runtime_tool_key
        ),
        None,
    )
    if capability is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tool key is not in the session capability manifest.",
        )
    if capability.is_external_execution:
        # ON owns this one. Executing it here would run it inside the runtime,
        # which is the very inversion Task 3.2 removed.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tool is executed by ON, not by the runtime.",
        )

    agent_record = (
        await storage.get_agent(request.user_id, session.agent_id)
        if session.agent_id
        else None
    )
    workspace = await workspace_manager.get_workspace(
        request.user_id,
        session.runtime_owner_id,
        request.session_id,
        session.config.workspace_id,
    )
    toolkit = await get_toolkit(
        storage=storage,
        workspace=workspace,
        scheduler_manager=scheduler_manager,
        background_task_manager=background_task_manager,
        message_bus=message_bus,
        user_id=request.user_id,
        agent_record=agent_record,
        session_record=session,
    )

    tool = next(
        (
            registered
            for group in toolkit.tool_groups
            for registered in group.tools
            if registered.name == capability.function_name
        ),
        None,
    )
    if tool is None:
        # The manifest authorised a Tool the runtime does not actually have.
        # That is a deployment mismatch, not a caller error.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Tool '{capability.function_name}' is authorised but not "
                "available in this runtime."
            ),
        )

    try:
        chunk = await tool.call(**request.arguments)
    except Exception as error:  # pylint: disable=broad-except
        # A failing Tool is a result, not a transport failure: ON records it
        # against the invocation and lets the workflow's error port decide.
        return ToolExecResponse(
            invocation_id=request.invocation_id,
            state="error",
            output=[{"type": "text", "text": str(error)}],
        )

    return ToolExecResponse(
        invocation_id=request.invocation_id,
        state="success",
        output=[block.model_dump(mode="json") for block in chunk.content],
        metadata=dict(chunk.metadata or {}),
    )
