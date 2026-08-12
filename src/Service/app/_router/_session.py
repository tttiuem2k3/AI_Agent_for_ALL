# -*- coding: utf-8 -*-
"""Session router — create, list, update, delete, stream, and get messages."""
import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from Common._utils._common import _generate_id
from ..deps import (
    get_current_user_id,
    get_message_bus,
    get_session_service,
    get_storage,
)
from ._schema import (
    CancelSessionResponse,
    InterruptSessionResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    ListMessagesResponse,
    ListSessionsResponse,
    SessionStatusResponse,
    SessionView,
    TeamDetailResponse,
    TeamMemberView,
    UpdateSessionRequest,
)
from ..message_bus import MessageBus, MessageBusKeys
from .._service import SessionService, SessionProjection, SubagentHitlProjector
from .._service._model import get_model
from ..storage import (
    AgentRecord,
    AgentRuntimeProfile,
    CapabilityManifest,
    CapabilityManifestV2,
    ChatModelConfig,
    DirectModelRuntimeProfile,
    TTSModelConfig,
    SessionConfig,
    SessionRecord,
    StorageBase,
    TeamRecord,
)
from Runtime.message import ToolCallState
from Runtime.event import CustomEvent


async def _build_team_detail(
    storage: StorageBase,
    user_id: str,
    team: TeamRecord,
) -> TeamDetailResponse:
    """Resolve a team's leader agent + member agents into a
    :class:`TeamDetailResponse` for the session list endpoint.

    Args:
        storage (`StorageBase`):
            app storage. Used to look up the leader session,
            each member agent, and each member's session.
        user_id (`str`):
            The owner user id.
        team (`TeamRecord`):
            The team to resolve. Caller has already loaded it.

    Returns:
        `TeamDetailResponse`:
            The team plus its resolved leader and member agents (each
            member paired with its session id when available).
    """
    leader_agent: AgentRecord | None = None
    leader_session = await storage.get_session(user_id, "", team.session_id)
    if leader_session is not None:
        leader_agent = await storage.get_agent(
            user_id,
            leader_session.agent_id,
        )

    members: list[TeamMemberView] = []
    for member_id in team.data.member_ids:
        agent = await storage.get_agent(user_id, member_id)
        if agent is None:
            continue
        sessions = await storage.list_sessions(user_id, member_id)
        session_id = sessions[0].id if sessions else None
        members.append(TeamMemberView(agent=agent, session_id=session_id))

    return TeamDetailResponse(
        team=team,
        leader_agent=leader_agent,
        members=members,
    )


session_router = APIRouter(
    prefix="/sessions",
    tags=["sessions"],
    responses={404: {"description": "Not found"}},
)


async def _get_owned_session(
    storage: StorageBase,
    user_id: str,
    session_id: str,
    agent_id: str | None,
    runtime_subject_id: str | None,
) -> SessionRecord | None:
    """Resolve a session and enforce its discriminated runtime identity."""
    if bool(agent_id) == bool(runtime_subject_id):
        return None
    record = await storage.get_session(user_id, agent_id, session_id)
    if record is None:
        return None
    if agent_id is not None and record.agent_id != agent_id:
        return None
    if (
        runtime_subject_id is not None
        and record.runtime_subject_id != runtime_subject_id
    ):
        return None
    return record


@session_router.post(
    "/{session_id}/cancel",
    response_model=CancelSessionResponse,
    summary="Cancel the active run for a session",
)
async def cancel_session_run(
    session_id: str,
    agent_id: str | None = Query(
        default=None,
        description="Agent that owns an Agent-mode session.",
    ),
    runtime_subject_id: str | None = Query(
        default=None,
        description="Runtime subject that owns a DirectModel session.",
    ),
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    service: SessionService = Depends(get_session_service),
) -> CancelSessionResponse:
    """Cancel a run idempotently after verifying session ownership."""
    existing = await _get_owned_session(
        storage,
        user_id,
        session_id,
        agent_id,
        runtime_subject_id,
    )
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )

    cancelled = await service.cancel_session_run(session_id)
    return CancelSessionResponse(
        session_id=session_id,
        status="cancelled" if cancelled else "cancel_requested",
    )


@session_router.post(
    "/{session_id}/interrupt",
    response_model=InterruptSessionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Interrupt the active or parked run for a session",
)
async def interrupt_session(
    session_id: str,
    agent_id: str | None = Query(default=None),
    runtime_subject_id: str | None = Query(default=None),
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    service: SessionService = Depends(get_session_service),
) -> InterruptSessionResponse:
    """Request interruption without changing the existing cancel route."""
    existing = await _get_owned_session(
        storage,
        user_id,
        session_id,
        agent_id,
        runtime_subject_id,
    )
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )
    await service.cancel_session_run(session_id)
    return InterruptSessionResponse(session_id=session_id)


async def _ensure_credential_exists(
    storage: StorageBase,
    user_id: str,
    config: ChatModelConfig | TTSModelConfig | None,
) -> None:
    """Validate that the credential referenced by ``config`` belongs to the
    given user. No-op when ``config`` is ``None``.

    Args:
        storage (`StorageBase`): Injected storage backend.
        user_id (`str`): The authenticated user ID.
        config (`ChatModelConfig | TTSModelConfig | None`): Model config to
            validate. Pass ``None`` to skip the check.

    Raises:
        `HTTPException`: 404 if the credential does not exist or does not
            belong to the user.
    """
    if config is None:
        return
    if isinstance(config, ChatModelConfig):
        # Model construction performs adapter/credential/model/parameter
        # validation without making a provider API call. This fails fast at
        # session create/update instead of waiting for the first chat run.
        await get_model(user_id, config, storage)
        return
    credentials = await storage.list_credentials(user_id)
    if not any(c.id == config.credential_id for c in credentials):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Credential '{config.credential_id}' not found.",
        )


@session_router.get(
    "/",
    response_model=ListSessionsResponse,
    summary="List sessions for an agent",
)
async def list_sessions(
    agent_id: str | None = Query(
        default=None,
        description="Filter Agent-mode sessions by Agent ID.",
    ),
    runtime_subject_id: str | None = Query(
        default=None,
        description="Filter DirectModel sessions by runtime subject.",
    ),
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    message_bus: MessageBus = Depends(get_message_bus),
) -> ListSessionsResponse:
    """Return all sessions for an agent as enriched
    :class:`SessionView` entries.

    Each entry bundles three things the chat UI needs to render
    without follow-up requests: the session record (incl.
    ``state``), whether a chat run is currently active, and — when
    the session participates in a team — the resolved team detail
    (leader agent + member agents with their session ids).

    Args:
        agent_id (`str`):
            Agent whose sessions to list.
        user_id (`str`):
            Injected authenticated user ID.
        storage (`StorageBase`):
            Injected storage backend.
        message_bus (`MessageBus`):
            Injected message bus (used for ``session_is_running``).

    Returns:
        `ListSessionsResponse`:
            Enriched session views and their count.

    Raises:
        `HTTPException`: 404 if the agent does not exist or does not
            belong to the authenticated user.
    """
    # Direct ownership check via get_agent — handles both source=user
    # and source=team agents (the latter aren't returned by
    # storage.list_agents but are still owned by the user; reachable
    # via team navigation).
    if bool(agent_id) == bool(runtime_subject_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide exactly one runtime identity.",
        )
    if agent_id is not None:
        agent = await storage.get_agent(user_id, agent_id)
        if agent is None or agent.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{agent_id}' not found.",
            )
        index_owner = agent_id
    else:
        index_owner = f"direct_model__{runtime_subject_id}"

    sessions = await storage.list_sessions(user_id, index_owner)
    views: list[SessionView] = []
    for session in sessions:
        team_detail = None
        if session.team_id:
            team_record = await storage.get_team(user_id, session.team_id)
            if team_record is not None:
                team_detail = await _build_team_detail(
                    storage,
                    user_id,
                    team_record,
                )
        views.append(
            SessionView(
                session=session,
                is_running=await message_bus.is_locked(
                    MessageBusKeys.session_lock(session.id),
                ),
                team=team_detail,
            ),
        )
    return ListSessionsResponse(sessions=views, total=len(views))


@session_router.post(
    "/",
    response_model=CreateSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new session",
)
async def create_session(
    body: CreateSessionRequest,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> CreateSessionResponse:
    """Create (or resume) a session for a given agent and workspace.

    At most one session exists per ``(user_id, agent_id, workspace_id)``
    triple — a second call with the same triple updates the existing session
    rather than creating a duplicate.

    Args:
        body (`CreateSessionRequest`): Agent, workspace, and model config.
        user_id (`str`): Injected authenticated user ID.
        storage (`StorageBase`): Injected storage backend.

    Returns:
        `CreateSessionResponse`: The session identifier.

    Raises:
        `HTTPException`: 404 if the agent or credential does not exist or
            does not belong to the authenticated user.
    """
    runtime_profile = body.runtime_profile
    assert runtime_profile is not None

    if isinstance(runtime_profile, AgentRuntimeProfile):
        agent = await storage.get_agent(user_id, runtime_profile.agent_id)
        if agent is None or agent.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{runtime_profile.agent_id}' not found.",
            )
        if (
            body.effective_capabilities is not None
            and not isinstance(body.effective_capabilities, CapabilityManifest)
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Agent session requires capability manifest v1.",
            )
    elif isinstance(runtime_profile, DirectModelRuntimeProfile):
        effective = (
            body.effective_capabilities
            or runtime_profile.base_capabilities
        )
        if not isinstance(effective, CapabilityManifestV2):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="DirectModel session requires capability manifest v2.",
            )
        base = runtime_profile.base_capabilities
        if (
            effective.subject_type != "DirectModel"
            or effective.subject_id != base.subject_id
            or effective.user_id != base.user_id
            or effective.division_id != base.division_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="DirectModel capability binding does not match session.",
            )
        base_tools = {
            tool.tool_id: tool.model_dump(mode="json")
            for tool in base.tools
        }
        base_skills = {
            skill.skill_id: skill.model_dump(mode="json")
            for skill in base.skills
        }
        if any(
            base_tools.get(tool.tool_id) != tool.model_dump(mode="json")
            for tool in effective.tools
        ) or any(
            base_skills.get(skill.skill_id) != skill.model_dump(mode="json")
            for skill in effective.skills
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "DirectModel effective capabilities are not an exact "
                    "subset of the session base manifest."
                ),
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported runtime profile.",
        )

    await _ensure_credential_exists(storage, user_id, body.chat_model_config)
    await _ensure_credential_exists(
        storage,
        user_id,
        body.fallback_chat_model_config,
    )
    await _ensure_credential_exists(storage, user_id, body.tts_model_config)

    session_record = await storage.upsert_session(
        user_id=user_id,
        agent_id=body.agent_id,
        config=SessionConfig(
            workspace_id=body.workspace_id or _generate_id(),
            chat_model_config=body.chat_model_config,
            fallback_chat_model_config=body.fallback_chat_model_config,
            tts_model_config=body.tts_model_config,
            effective_capabilities=(
                body.effective_capabilities
                if body.effective_capabilities is not None
                else (
                    runtime_profile.base_capabilities
                    if isinstance(
                        runtime_profile,
                        DirectModelRuntimeProfile,
                    )
                    else None
                )
            ),
            **({"name": body.name} if body.name is not None else {}),
        ),
        runtime_profile=runtime_profile,
        runtime_subject_id=body.runtime_subject_id,
    )
    return CreateSessionResponse(
        session_id=session_record.id,
        runtime_subject_id=session_record.runtime_subject_id,
    )


@session_router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a session",
)
async def delete_session(
    session_id: str,
    agent_id: str | None = Query(
        default=None,
        description="Agent the session belongs to.",
    ),
    runtime_subject_id: str | None = Query(
        default=None,
        description="DirectModel runtime subject.",
    ),
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    session_service: SessionService = Depends(get_session_service),
) -> None:
    """Permanently delete a session and all its associated state.

    Cancels any in-flight chat run for this session (and for every
    worker session if this one is a team leader) before dropping
    storage records and bus state. The cancel path is cross-process:
    whichever worker is actually running the session will receive the
    cancel broadcast and abort.

    Args:
        session_id (`str`): The session to delete.
        agent_id (`str`): The agent the session belongs to.
        user_id (`str`): Injected authenticated user ID.
        session_service (`SessionService`): Injected session service.

    Raises:
        `HTTPException`: 404 if the session does not exist or does not belong
            to the authenticated user.
    """
    existing = await _get_owned_session(
        storage,
        user_id,
        session_id,
        agent_id,
        runtime_subject_id,
    )
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )

    deleted = await session_service.delete_session(
        user_id,
        agent_id,
        session_id,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )


@session_router.patch(
    "/{session_id}",
    response_model=SessionRecord,
    summary="Update a session",
)
async def update_session(
    session_id: str,
    body: UpdateSessionRequest,
    agent_id: str | None = Query(
        default=None,
        description="Agent the session belongs to.",
    ),
    runtime_subject_id: str | None = Query(
        default=None,
        description="DirectModel runtime subject.",
    ),
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> SessionRecord:
    """Update the model configuration of an existing session.

    Args:
        session_id (`str`): The session to update.
        body (`UpdateSessionRequest`): Fields to update.
        user_id (`str`): Injected authenticated user ID.
        storage (`StorageBase`): Injected storage backend.

    Returns:
        `SessionRecord`: The full session record after the update.

    Raises:
        `HTTPException`: 404 if the session, agent, or credential does not
            exist or does not belong to the authenticated user.
    """
    existing = await _get_owned_session(
        storage,
        user_id,
        session_id,
        agent_id,
        runtime_subject_id,
    )
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )

    replacement_profile = body.runtime_profile
    if replacement_profile is not None:
        if not isinstance(existing.runtime_profile, DirectModelRuntimeProfile):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Agent runtime profiles cannot be replaced.",
            )
        if not isinstance(replacement_profile, DirectModelRuntimeProfile):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="DirectModel session requires a DirectModel profile.",
            )
        if (
            replacement_profile.base_capabilities.subject_id
            != existing.runtime_subject_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="DirectModel runtime subject is immutable.",
            )

    effective = body.effective_capabilities
    profile_for_validation = replacement_profile or existing.runtime_profile
    if isinstance(profile_for_validation, DirectModelRuntimeProfile):
        if effective is not None and not isinstance(
            effective,
            CapabilityManifestV2,
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="DirectModel session requires capability manifest v2.",
            )
        candidate = effective or existing.config.effective_capabilities
        if isinstance(candidate, CapabilityManifestV2):
            base = profile_for_validation.base_capabilities
            base_tools = {
                tool.tool_id: tool.model_dump(mode="json")
                for tool in base.tools
            }
            base_skills = {
                skill.skill_id: skill.model_dump(mode="json")
                for skill in base.skills
            }
            if (
                candidate.subject_id != base.subject_id
                or candidate.user_id != base.user_id
                or candidate.division_id != base.division_id
                or any(
                    base_tools.get(tool.tool_id)
                    != tool.model_dump(mode="json")
                    for tool in candidate.tools
                )
                or any(
                    base_skills.get(skill.skill_id)
                    != skill.model_dump(mode="json")
                    for skill in candidate.skills
                )
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "DirectModel effective capabilities are not an exact "
                        "subset of the replacement base manifest."
                    ),
                )

    await _ensure_credential_exists(storage, user_id, body.chat_model_config)
    await _ensure_credential_exists(
        storage,
        user_id,
        body.fallback_chat_model_config,
    )
    await _ensure_credential_exists(storage, user_id, body.tts_model_config)

    updated_state = existing.state
    if body.permission_mode is not None:
        updated_ctx = existing.state.permission_context.model_copy(
            update={"mode": body.permission_mode},
        )

        updated_state = existing.state.model_copy(
            update={
                "permission_context": updated_ctx,
            },
        )

    # PATCH semantics: only fields explicitly present in the request body are
    # applied. ``exclude_unset=True`` lets clients distinguish "leave
    # unchanged" (omit) from "clear" (send ``null``) — required for clearing
    # ``fallback_chat_model_config``.
    config_updates = body.model_dump(
        exclude_unset=True,
        exclude={"permission_mode", "runtime_profile"},
    )

    return await storage.upsert_session(
        user_id=user_id,
        agent_id=agent_id,
        config=SessionConfig.model_validate(
            {**existing.config.model_dump(mode="json"), **config_updates},
        ),
        state=updated_state,
        session_id=session_id,
        runtime_profile=replacement_profile or existing.runtime_profile,
        runtime_subject_id=existing.runtime_subject_id,
    )


# ----------------------------------------------------------------------
# Messages: fetch persisted messages for a session
# ----------------------------------------------------------------------


@session_router.get(
    "/{session_id}/messages",
    response_model=ListMessagesResponse,
    summary="List messages for a session",
)
async def list_messages(
    session_id: str,
    agent_id: str | None = Query(
        default=None,
        description="Agent the session belongs to.",
    ),
    runtime_subject_id: str | None = Query(
        default=None,
        description="DirectModel runtime subject.",
    ),
    offset: int = Query(0, ge=0, description="Pagination offset."),
    limit: int = Query(50, ge=1, le=200, description="Max messages."),
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    message_bus: MessageBus = Depends(get_message_bus),
) -> ListMessagesResponse:
    """Return persisted messages for a session.

    Args:
        session_id: The session to query.
        agent_id: Agent the session belongs to.
        offset: Pagination offset.
        limit: Maximum number of messages to return.
        user_id: Injected authenticated user ID.
        storage: Injected storage backend.
        message_bus: Injected message bus.

    Returns:
        Messages and running status.
    """
    existing = await _get_owned_session(
        storage,
        user_id,
        session_id,
        agent_id,
        runtime_subject_id,
    )
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )

    messages = await storage.list_messages(
        user_id,
        session_id,
        offset=offset,
        limit=limit,
    )
    return ListMessagesResponse(
        messages=messages,
        is_running=await message_bus.is_locked(
            MessageBusKeys.session_lock(session_id),
        ),
    )


@session_router.get(
    "/{session_id}/status",
    response_model=SessionStatusResponse,
    summary="Probe the session's high-level status",
)
async def get_session_status(
    session_id: str,
    agent_id: str | None = Query(default=None),
    runtime_subject_id: str | None = Query(default=None),
    user_id: str = Depends(get_current_user_id),
    service: SessionService = Depends(get_session_service),
) -> SessionStatusResponse:
    """Return running, idle, permission-waiting, or external-waiting."""
    session_status = await service.get_session_status(
        user_id,
        session_id,
        agent_id=agent_id,
        runtime_subject_id=runtime_subject_id,
    )
    if session_status is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )
    return SessionStatusResponse(
        session_id=session_id,
        status=session_status,
    )


# ----------------------------------------------------------------------
# Stream: live SSE connection for session events
# ----------------------------------------------------------------------

_HEARTBEAT_INTERVAL_SECS = 30
# Interval between SSE heartbeat comment frames (``:\\n\\n``).


async def _worker_still_asking(
    storage: StorageBase,
    user_id: str,
    worker_agent_id: str,
    worker_session_id: str,
    reply_id: str,
) -> bool:
    """Return whether a worker session is still parked on the ASKING
    tool call identified by ``reply_id``.

    This is the reconcile-on-read check (design §3.5): the worker
    session's own ``state.context`` is the single source of truth for
    "does this confirmation still need answering". A leader-side
    pending projection whose worker has already resolved / cancelled
    the call is a ghost and must not be replayed.

    Mirrors the wakeup guard in
    :meth:`ChatService._run_impl` — a request is "still asking" when
    the tail ``AssistantMsg`` of the worker carries a tool call in
    ``ASKING`` or ``SUBMITTED`` state for the matching ``reply_id``.

    Args:
        storage (`StorageBase`):
            app storage.
        user_id (`str`):
            The owner user id.
        worker_agent_id (`str`):
            The worker agent that owns the session.
        worker_session_id (`str`):
            The worker session to inspect.
        reply_id (`str`):
            The reply id the pending request belongs to.

    Returns:
        `bool`:
            ``True`` if the worker is still awaiting confirmation for
            ``reply_id``; ``False`` otherwise (resolved, cancelled, or
            the session/record is gone).
    """
    session = await storage.get_session(
        user_id,
        worker_agent_id,
        worker_session_id,
    )
    if session is None or not session.state.context:
        return False
    last_msg = session.state.context[-1]
    if last_msg.role != "assistant" or last_msg.id != reply_id:
        return False
    return any(
        tc.state in (ToolCallState.ASKING, ToolCallState.SUBMITTED)
        for tc in last_msg.get_content_blocks("tool_call")
    )


@session_router.get(
    "/{session_id}/stream",
    summary="Subscribe to a session's event stream (SSE)",
    response_description="Server-Sent Events stream of AgentEvent objects",
)
async def stream_session_events(
    session_id: str,
    agent_id: str | None = Query(
        default=None,
        description="Agent the session belongs to.",
    ),
    runtime_subject_id: str | None = Query(
        default=None,
        description="DirectModel runtime subject.",
    ),
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
    message_bus: MessageBus = Depends(get_message_bus),
) -> StreamingResponse:
    """Subscribe to a session's live event stream.

    Returns a ``text/event-stream`` that first replays any buffered
    events from the current run's replay log (if a run is in progress
    or just finished), then streams live events as they are produced
    by :meth:`ChatService.run`. The connection stays open
    until the client disconnects — subsequent runs on the same session
    are delivered over the same connection.

    A heartbeat comment frame (``:\\n\\n``) is sent every 30 seconds to
    keep the connection alive through reverse proxies.

    Args:
        session_id (`str`):
            The session to subscribe to.
        agent_id (`str`):
            The agent that owns the session (used for ownership
            validation).
        user_id (`str`):
            Injected authenticated user id.
        storage (`StorageBase`):
            Injected storage backend (ownership check only).
        message_bus (`MessageBus`):
            Injected message bus (replay + live subscription).

    Returns:
        `StreamingResponse`:
            SSE stream of AgentEvent frames + periodic heartbeats.
    """
    existing = await _get_owned_session(
        storage,
        user_id,
        session_id,
        agent_id,
        runtime_subject_id,
    )
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )

    async def _sse_generator() -> AsyncGenerator[str, None]:
        # 1. Replay buffered events from the current run (if any).
        for _entry_id, event in await message_bus.log_read(
            MessageBusKeys.session_events(session_id),
            max_count=MessageBusKeys.SESSION_REPLAY_MAX_LEN,
        ):
            yield f"data: {json.dumps(event)}\n\n"

        # 1b. Inject pending subagent HITL cards projected onto this
        #     session as a team leader (design §3.5). These live in a
        #     durable Redis hash — NOT in the replay log (trimmed per
        #     run) nor in the leader's own Msg history — so a fresh
        #     reconnect after the worker parked still surfaces them.
        #
        #     Reconcile-on-read: the worker session's own context is the
        #     SSOT. Inject only when the worker is still ASKING; drop and
        #     delete ghosts (worker resolved/cancelled without clearing).
        projection = SessionProjection(message_bus)
        for payload in await projection.list(
            session_id,
            SubagentHitlProjector.KIND,
        ):
            if not await _worker_still_asking(
                storage,
                user_id,
                payload["worker_agent_id"],
                payload["worker_session_id"],
                payload["reply_id"],
            ):
                await projection.delete(
                    session_id,
                    SubagentHitlProjector.KIND,
                    SubagentHitlProjector.entry_id(
                        payload["worker_session_id"],
                        payload["reply_id"],
                    ),
                )
                continue
            custom = CustomEvent(
                name=SubagentHitlProjector.EVT_REQUIRE,
                value=payload,
            )
            yield f"data: {json.dumps(custom.model_dump(mode='json'))}\n\n"

        # 2. Live subscribe via a background feeder task that pushes
        #    events into a queue. The main loop reads from the queue
        #    with a timeout so we can interleave heartbeat frames.
        #
        #    We avoid calling ``wait_for(__anext__())`` on the async
        #    generator directly because cancelling a suspended
        #    ``__anext__`` leaves the generator in a "running" state
        #    that prevents ``aclose()`` from working.
        queue: asyncio.Queue[dict | None] = asyncio.Queue()

        async def _feeder() -> None:
            """Read from the bus subscription and forward to the queue.

            Pushes ``None`` as a sentinel when the subscription ends
            (which in practice only happens if the bus shuts down).
            """
            try:
                async for evt in message_bus.subscribe(
                    MessageBusKeys.session_events(session_id),
                ):
                    await queue.put(
                        {k: v for k, v in evt.items() if k != "_entry_id"},
                    )
            except asyncio.CancelledError:
                pass
            finally:
                await queue.put(None)

        feeder_task = asyncio.create_task(
            _feeder(),
            name=f"sse-feeder:{session_id}",
        )

        try:
            while True:
                try:
                    item = await asyncio.wait_for(
                        queue.get(),
                        timeout=_HEARTBEAT_INTERVAL_SECS,
                    )
                    if item is None:
                        break
                    yield f"data: {json.dumps(item)}\n\n"
                except asyncio.TimeoutError:
                    yield ":\n\n"
        finally:
            feeder_task.cancel()
            try:
                await feeder_task
            except asyncio.CancelledError:
                pass

    return StreamingResponse(
        _sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
