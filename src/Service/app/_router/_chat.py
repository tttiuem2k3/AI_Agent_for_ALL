# -*- coding: utf-8 -*-
"""Chat router — fire-and-forget trigger for chat runs.

The endpoint no longer returns an SSE stream. Instead, it kicks off a
chat run as a background task and returns immediately. Events produced
by the run are published to the message bus and delivered to the
frontend via the long-lived ``GET /sessions/{sid}/stream`` SSE
connection provided by the session router.

Two trigger paths, deliberately asymmetric:

- **New user message(s)** are spawned directly into the
  :class:`ChatRunRegistry`. The registry's single-run-per-session rule
  surfaces as a 409, which is exactly the desired double-submit guard.
- **HITL results** (``UserConfirmResultEvent`` /
  ``ExternalExecutionResultEvent``) are *enqueued* onto the shared
  run-trigger queue and drained by the single
  :class:`WakeupDispatcher`. Routing the resume through the queue keeps
  the dispatcher the sole spawn site, so a resume can never collide with
  the worker's still-finishing parked run (the old 409 race) — the
  dispatcher serialises them.
"""
from fastapi import APIRouter, Depends, HTTPException, status

from ..deps import (
    get_chat_run_registry,
    get_chat_service,
    get_current_user_id,
    get_message_bus,
    get_storage,
)
from ._schema import ChatRequest, ChatTriggerResponse
from .._manager import ChatRunRegistry
from .._service import (
    ChatService,
    SessionProjection,
    SubagentHitlProjector,
)
from ..message_bus import MessageBus, MessageBusKeys
from ..storage import (
    CapabilityManifest,
    CapabilityManifestV2,
    DirectModelRuntimeProfile,
    StorageBase,
)
from .._bus_ops import enqueue_run_trigger
from Runtime.event import UserConfirmResultEvent, ExternalExecutionResultEvent

chat_router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    responses={404: {"description": "Not found"}},
)


async def _refresh_effective_capabilities(
    request: ChatRequest,
    user_id: str,
    storage: StorageBase,
) -> None:
    """Validate and persist a fresh ERPX capability snapshot before a run."""
    manifest = request.effective_capabilities
    if manifest is None:
        if request.runtime_subject_id is None:
            return
        session = await storage.get_session(
            user_id,
            None,
            request.session_id,
        )
        if (
            session is None
            or session.runtime_subject_id != request.runtime_subject_id
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="DirectModel runtime session was not found.",
            )
        if not isinstance(
            request.input,
            (UserConfirmResultEvent, ExternalExecutionResultEvent),
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "DirectModel chat requires a fresh capability "
                    "manifest v2."
                ),
            )
        return

    session = await storage.get_session(
        user_id,
        request.agent_id,
        request.session_id,
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ERPX runtime session was not found.",
        )

    if session.agent_id is not None:
        if (
            request.agent_id != session.agent_id
            or not isinstance(manifest, CapabilityManifest)
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="ERPX Agent/session capability binding was not found.",
            )
        agent = await storage.get_agent(user_id, session.agent_id)
        if agent is None or agent.data.base_capabilities is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ERPX Agent capability binding was not found.",
            )
        base = agent.data.base_capabilities
        session_binding = session.config.effective_capabilities
        if (
            (
                isinstance(session_binding, CapabilityManifest)
                and manifest.user_id != session_binding.user_id
            )
            or manifest.agent_apk != base.agent_apk
            or manifest.agent_id != base.agent_id
            or manifest.division_id != base.division_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "ERPX capability manifest does not match its "
                    "Agent/session."
                ),
            )
    else:
        profile = session.runtime_profile
        if (
            not isinstance(profile, DirectModelRuntimeProfile)
            or not isinstance(manifest, CapabilityManifestV2)
            or request.runtime_subject_id != session.runtime_subject_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="DirectModel runtime binding was not found.",
            )
        base = profile.base_capabilities
        session_binding = session.config.effective_capabilities
        if (
            manifest.subject_type != "DirectModel"
            or manifest.subject_id != session.runtime_subject_id
            or manifest.subject_id != base.subject_id
            or manifest.user_id != base.user_id
            or manifest.division_id != base.division_id
            or (
                isinstance(session_binding, CapabilityManifestV2)
                and (
                    manifest.user_id != session_binding.user_id
                    or manifest.division_id != session_binding.division_id
                    or manifest.subject_id != session_binding.subject_id
                )
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "DirectModel capability manifest does not match its "
                    "session."
                ),
            )

    base_tools = {tool.tool_id: tool for tool in base.tools}
    for effective_tool in manifest.tools:
        base_tool = base_tools.get(effective_tool.tool_id)
        if (
            base_tool is None
            or effective_tool.model_dump(mode="json")
            != base_tool.model_dump(mode="json")
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "ERPX effective capabilities are not a subset of "
                    "Agent base capabilities."
                ),
            )

    base_skills = {skill.skill_id: skill for skill in base.skills}
    for effective_skill in manifest.skills:
        base_skill = base_skills.get(effective_skill.skill_id)
        if (
            base_skill is None
            or effective_skill.model_dump(mode="json")
            != base_skill.model_dump(mode="json")
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "ERPX effective Skills are not a subset of Agent "
                    "base capabilities."
                ),
            )

    await storage.upsert_session(
        user_id=user_id,
        agent_id=request.agent_id,
        config=session.config.model_copy(
            update={
                "effective_capabilities": manifest,
                "runtime_run_id": request.runtime_run_id,
            },
        ),
        state=session.state,
        session_id=request.session_id,
        runtime_profile=session.runtime_profile,
        runtime_subject_id=session.runtime_subject_id,
    )


@chat_router.post(
    "/",
    response_model=ChatTriggerResponse,
    summary="Trigger a chat run (fire-and-forget)",
)
async def chat(
    request: ChatRequest,
    user_id: str = Depends(get_current_user_id),
    chat_service: ChatService = Depends(get_chat_service),
    chat_run_registry: ChatRunRegistry = Depends(get_chat_run_registry),
    message_bus: MessageBus = Depends(get_message_bus),
    storage: StorageBase = Depends(get_storage),
) -> ChatTriggerResponse:
    """Trigger a chat run for the specified session.

    Events produced during the run are published to the message bus and
    delivered to any active ``GET /sessions/{session_id}/stream`` SSE
    subscriber. The caller does **not** receive events from this
    endpoint's response body.

    Accepts the same ``input`` payloads as before:

    - ``Msg`` / ``list[Msg]``: new user message(s) — spawned directly.
    - ``UserConfirmResultEvent`` / ``ExternalExecutionResultEvent``:
      resume a paused tool call (human-in-the-loop) — routed to the
      owning session and enqueued for the dispatcher.
    - ``None``: continue from current state — spawned directly.

    Args:
        request (`ChatRequest`):
            JSON body with ``agent_id``, ``session_id``, and ``input``.
        user_id (`str`):
            Injected user id.
        chat_service (`ChatService`):
            Injected app-wide chat service.
        chat_run_registry (`ChatRunRegistry`):
            Injected per-process chat-run registry.
        message_bus (`MessageBus`):
            Injected message bus, used to resolve subagent-confirm
            routing and to enqueue resume triggers.

    Returns:
        `ChatTriggerResponse`:
            Confirms the run was scheduled (for a resume, that it was
            enqueued).

    Raises:
        `HTTPException`:
            409 if a chat run for this session is already in flight in
            this process (the registry enforces single-run-per-session).
            Only direct-spawn paths (new messages / ``None``) can raise
            this; the enqueued resume path never does.
    """
    await _refresh_effective_capabilities(request, user_id, storage)

    request_reserved = False
    if request.request_id is not None:
        request_reserved = await storage.reserve_chat_request(
            user_id,
            request.session_id,
            request.request_id,
        )
        if not request_reserved:
            return ChatTriggerResponse(
                status="already_started",
                session_id=request.session_id,
            )

    # ------------------------------------------------------------------
    # HITL resume — route to the owning session, then enqueue.
    #
    # A confirmation / external-result POSTed to a *leader* session may
    # actually belong to a team *member*: the leader is the single front
    # door clients talk to. Resolve the owning worker HERE, then enqueue
    # a ``resume`` trigger for that session. The single WakeupDispatcher
    # drains it — spawning under the *worker* session id, serialised
    # behind any still-finishing parked run, so there is no registry
    # collision (no 409) and the leader's run slot is never occupied by
    # the worker's resume.
    # ------------------------------------------------------------------
    if isinstance(
        request.input,
        (UserConfirmResultEvent, ExternalExecutionResultEvent),
    ):
        run_session_id = request.session_id
        run_agent_id = request.agent_id
        run_runtime_subject_id = request.runtime_subject_id
        target = await SubagentHitlProjector.resolve(
            SessionProjection(message_bus),
            request.session_id,
            request.input.reply_id,
        )
        if target is not None:
            run_session_id = target["worker_session_id"]
            run_agent_id = target["worker_agent_id"]
            run_runtime_subject_id = None

        try:
            await enqueue_run_trigger(
                message_bus,
                user_id=user_id,
                session_id=run_session_id,
                agent_id=run_agent_id,
                runtime_subject_id=run_runtime_subject_id,
                kind=MessageBusKeys.WAKEUP_KIND_RESUME,
                inputs=request.input,
            )
        except Exception:
            if request_reserved:
                await storage.release_chat_request(
                    user_id,
                    request.session_id,
                    request.request_id,
                )
            raise
        return ChatTriggerResponse(status="started", session_id=run_session_id)

    # ------------------------------------------------------------------
    # New user message(s) / None — spawn directly. The registry's
    # single-run-per-session rule is the desired double-submit guard.
    # ------------------------------------------------------------------
    try:
        chat_run_registry.spawn(
            chat_service.run(
                user_id=user_id,
                session_id=request.session_id,
                agent_id=request.agent_id,
                runtime_subject_id=request.runtime_subject_id,
                input_msg=request.input,
            ),
            session_id=request.session_id,
        )
    except RuntimeError as e:
        if request_reserved:
            await storage.release_chat_request(
                user_id,
                request.session_id,
                request.request_id,
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    return ChatTriggerResponse(
        status="started",
        session_id=request.session_id,
    )
