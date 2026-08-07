# -*- coding: utf-8 -*-
"""Request/response models for the ON-only Tool execution endpoint."""
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ToolExecRequest(BaseModel):
    """One ON-authorised call of a Tool the Python runtime owns.

    ``extra="forbid"`` is the point of this model, not a nicety: the endpoint
    must never grow an accidental transport field.  Nothing here can name a
    URL, a module, a class or a callable — only a key ON already published in
    the session's capability manifest.
    """

    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(min_length=1, max_length=200)
    agent_id: str | None = None
    session_id: str = Field(min_length=1, max_length=200)

    invocation_id: str = Field(min_length=1, max_length=64)
    """``ONT2050.ApprovalID`` — echoed back so ON can match the reply."""

    runtime_tool_key: str = Field(min_length=1, max_length=40)
    """``ONT1020.ToolID``, resolved against the session manifest only."""

    arguments: dict[str, Any] = Field(default_factory=dict)
    """The approved argument snapshot. Never re-derived here."""


class ToolExecResponse(BaseModel):
    """Structured result, shaped like an AgentScope tool result block."""

    model_config = ConfigDict(extra="forbid")

    invocation_id: str
    state: str
    output: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
