# -*- coding: utf-8 -*-
"""The chat endpoint schema."""

from pydantic import BaseModel, Field, model_validator

from Runtime.message import Msg
from Runtime.event import UserConfirmResultEvent, ExternalExecutionResultEvent
from ...storage import CapabilitySnapshot


class ChatRequest(BaseModel):
    """Request body for the chat endpoint."""

    agent_id: str | None = Field(
        default=None,
        description="Agent ID for the chat endpoint.",
    )
    runtime_subject_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="DirectModel runtime subject.",
    )

    session_id: str = Field(
        description="The session to send the message to.",
    )

    request_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Optional durable idempotency key scoped to the session.",
    )

    effective_capabilities: CapabilitySnapshot | None = Field(
        default=None,
        description=(
            "Fresh ERPX user/division capability snapshot. Omitted by "
            "non-ERPX callers and legacy HITL resume requests."
        ),
    )

    runtime_run_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Trusted ERPX RunID used for Tool Gateway idempotency.",
    )

    input: (
        Msg
        | list[Msg]
        | UserConfirmResultEvent
        | ExternalExecutionResultEvent
        | None
    ) = Field(
        description="The input message(s), or agent event, or None.",
    )

    @model_validator(mode="after")
    def _validate_runtime_identity(self) -> "ChatRequest":
        if bool(self.agent_id) == bool(self.runtime_subject_id):
            raise ValueError(
                "Provide exactly one of agent_id or runtime_subject_id",
            )
        return self


class ChatTriggerResponse(BaseModel):
    """Response body for the fire-and-forget chat trigger.

    Confirms that the chat run was scheduled. Events produced by the
    run arrive separately via the session's SSE stream endpoint.
    """

    status: str = Field(
        default="started",
        description='``"started"`` or ``"already_started"`` for a replayed request id.',
    )
    session_id: str = Field(
        description="Echo of the session id the run was started for.",
    )
