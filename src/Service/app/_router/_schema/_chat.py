# -*- coding: utf-8 -*-
"""The chat endpoint schema."""

from pydantic import BaseModel, Field

from Runtime.message import Msg
from Runtime.event import UserConfirmResultEvent, ExternalExecutionResultEvent


class ChatRequest(BaseModel):
    """Request body for the chat endpoint."""

    agent_id: str = Field(
        description="Agent ID for the chat endpoint.",
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

    input: (
        Msg
        | list[Msg]
        | UserConfirmResultEvent
        | ExternalExecutionResultEvent
        | None
    ) = Field(
        description="The input message(s), or agent event, or None.",
    )


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
