# -*- coding: utf-8 -*-
"""Request / response schemas for the session router."""
from pydantic import BaseModel, Field, model_validator

from Capabilities.permission import PermissionMode
from ...storage import (
    AgentRecord,
    ChatModelConfig,
    TTSModelConfig,
    SessionRecord,
    TeamRecord,
    CapabilitySnapshot,
    AgentRuntimeProfile,
    DirectModelRuntimeProfile,
    RuntimeProfile,
)


class TeamMemberView(BaseModel):
    """One row in :attr:`TeamDetailResponse.members`.

    Pairs each member's :class:`AgentRecord` with its single
    ``session_id`` so the UI can subscribe to the worker's chat
    stream without a separate lookup.
    """

    agent: AgentRecord = Field(
        description="The worker agent record.",
    )
    session_id: str | None = Field(
        default=None,
        description=(
            "The worker's session id. ``None`` if the agent is in an "
            "inconsistent state (worker without a session)."
        ),
    )


class TeamDetailResponse(BaseModel):
    """Resolved team detail embedded inside :class:`SessionView.team`."""

    team: TeamRecord = Field(description="The team record.")
    leader_agent: AgentRecord | None = Field(
        default=None,
        description=(
            "Leader's agent record (resolved from the team's "
            "``session_id`` → session.agent_id)."
        ),
    )
    members: list[TeamMemberView] = Field(
        default_factory=list,
        description=(
            "Worker agents listed in :attr:`TeamData.member_ids`, each "
            "paired with its single session id when available."
        ),
    )


class CreateSessionRequest(BaseModel):
    """Request body for creating a new session."""

    agent_id: str | None = Field(
        default=None,
        description="Persisted Agent id. Omit for DirectModel.",
    )
    runtime_subject_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="Immutable DirectModel runtime subject.",
    )
    runtime_profile: RuntimeProfile | None = Field(
        default=None,
        description=(
            "Explicit runtime construction profile. Omitted legacy requests "
            "are interpreted as Agent sessions."
        ),
    )
    workspace_id: str | None = Field(
        default=None,
        description="Workspace this session belongs to.",
    )
    name: str | None = Field(
        default=None,
        description="Display name. Defaults to current datetime if omitted.",
    )
    chat_model_config: ChatModelConfig | None = Field(
        default=None,
        description="Model provider and parameters. "
        "Can be set later via PATCH.",
    )
    fallback_chat_model_config: ChatModelConfig | None = Field(
        default=None,
        description="Fallback model used when the primary model fails. "
        "Can be set later via PATCH.",
    )
    tts_model_config: TTSModelConfig | None = Field(
        default=None,
        description="TTS model configuration. Can be set later via PATCH.",
    )
    effective_capabilities: CapabilitySnapshot | None = Field(
        default=None,
        description="Effective ERPX capability snapshot for this session.",
    )

    @model_validator(mode="after")
    def _validate_runtime_shape(self) -> "CreateSessionRequest":
        if self.runtime_profile is None:
            if not self.agent_id:
                raise ValueError("Agent session requires agent_id")
            self.runtime_profile = AgentRuntimeProfile(agent_id=self.agent_id)
            if self.runtime_subject_id is not None:
                raise ValueError(
                    "Agent session cannot have runtime_subject_id",
                )
            return self

        if isinstance(self.runtime_profile, AgentRuntimeProfile):
            if self.agent_id != self.runtime_profile.agent_id:
                raise ValueError(
                    "Agent runtime profile does not match agent_id",
                )
            if self.runtime_subject_id is not None:
                raise ValueError(
                    "Agent session cannot have runtime_subject_id",
                )
            return self

        if isinstance(self.runtime_profile, DirectModelRuntimeProfile):
            if self.agent_id is not None:
                raise ValueError(
                    "DirectModel session cannot reference agent_id",
                )
            expected = self.runtime_profile.base_capabilities.subject_id
            if self.runtime_subject_id != expected:
                raise ValueError(
                    "DirectModel runtime subject does not match base manifest",
                )
            return self

        raise ValueError("Unsupported runtime profile")


class CreateSessionResponse(BaseModel):
    """Response body after creating a session."""

    session_id: str = Field(description="Server-assigned session identifier.")
    runtime_subject_id: str | None = Field(
        default=None,
        description="DirectModel runtime subject; null for Agent sessions.",
    )


class CancelSessionResponse(BaseModel):
    """Response body after requesting cancellation of a session run."""

    session_id: str = Field(description="Cancelled session identifier.")
    status: str = Field(
        description=(
            "Cancellation outcome: 'cancelled' when the distributed run "
            "lock cleared, otherwise 'cancel_requested'."
        ),
    )


class UpdateSessionRequest(BaseModel):
    """Request body for updating an existing session.

    Omit any field to keep its current value.
    """

    name: str | None = Field(
        default=None,
        description="New display name.",
    )
    chat_model_config: ChatModelConfig | None = Field(
        default=None,
        description="New model configuration. "
        "Replaces the existing one entirely. "
        "Pass null to clear; omit to leave unchanged.",
    )
    fallback_chat_model_config: ChatModelConfig | None = Field(
        default=None,
        description="New fallback model configuration. "
        "Pass null to clear; omit to leave unchanged.",
    )
    tts_model_config: TTSModelConfig | None = Field(
        default=None,
        description="New TTS model configuration. "
        "Pass null to clear; omit to leave unchanged.",
    )
    permission_mode: PermissionMode | None = Field(
        default=None,
        description="New permission mode for the session.",
    )
    effective_capabilities: CapabilitySnapshot | None = Field(
        default=None,
        description="Replacement effective ERPX capability snapshot.",
    )
    runtime_profile: RuntimeProfile | None = Field(
        default=None,
        description=(
            "Trusted replacement runtime profile. Only DirectModel callers "
            "may replace the profile to synchronize base capabilities."
        ),
    )


class SessionView(BaseModel):
    """Per-session bundle with everything the frontend needs to
    render either the list view or open a session.

    Bundles three orthogonal pieces of information so opening a
    session does not require a waterfall of follow-up requests:

    - the persisted :class:`SessionRecord` itself (config + state),
    - whether the session has an active chat run right now,
    - the team detail (resolved leader + members) when the session
      participates in a team.

    Messages are intentionally **not** included here — they are
    paginated separately via ``GET /sessions/{id}/messages``.
    """

    session: SessionRecord = Field(
        description=(
            "The persisted session record. Includes ``state`` "
            "(``permission_context`` / ``tool_context`` / "
            "``tasks_context``) inline."
        ),
    )
    is_running: bool = Field(
        description="Whether a chat run is currently active on this session.",
    )
    team: TeamDetailResponse | None = Field(
        default=None,
        description=(
            "Resolved team detail when ``session.team_id`` is set "
            "(leader agent + member agents with their session ids). "
            "``None`` when the session does not participate in any team."
        ),
    )


class ListSessionsResponse(BaseModel):
    """Response body for listing sessions."""

    sessions: list[SessionView] = Field(
        description="Session views (record + is_running + team).",
    )
    total: int = Field(description="Total number of sessions.")


class ListMessagesResponse(BaseModel):
    """Response body for listing messages in a session."""

    messages: list = Field(description="Messages in chronological order.")
    is_running: bool = Field(
        description="Whether the session is currently running.",
    )
