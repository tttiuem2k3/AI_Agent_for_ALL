# -*- coding: utf-8 -*-
"""The session data class for storage."""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator

from ._base import _RecordBase
from ._capability import CapabilitySnapshot
from ._runtime import (
    AgentRuntimeProfile,
    DirectModelRuntimeProfile,
    RuntimeProfile,
)
from Runtime.state import AgentState


class SessionSource(str, Enum):
    """The source that created the session."""

    USER = "user"
    SCHEDULE = "schedule"


class ChatModelConfig(BaseModel):
    """The model configuration class."""

    type: str | None = None
    """Legacy provider type; retained for stored-session compatibility."""

    model_adapter: str | None = None
    """Runtime adapter key, e.g. ``openai_response``."""

    credential_id: str
    """The credential id."""

    model: str
    """The model name."""

    context_size: int | None = Field(default=None, gt=0)
    """Context window used by runtime context compression."""

    parameters: dict = Field(default_factory=dict)
    """The model parameters."""


class TTSModelConfig(BaseModel):
    """The TTS model configuration class."""

    type: str
    """The provider type."""

    credential_id: str
    """The credential id."""

    model: str
    """The TTS model name."""

    parameters: dict
    """TTS parameters (voice, language, etc.)."""


class EmbeddingModelConfig(BaseModel):
    """Configuration for constructing an embedding model from a credential.

    Mirrors :class:`ChatModelConfig` but targets
    :class:`~ASOFT.embedding.EmbeddingModelBase` subclasses.
    Used by :class:`KnowledgeBaseRecord` to persist the user's
    embedding model selection.
    """

    type: str
    """The provider type (e.g. ``"openai_credential"``)."""

    credential_id: str
    """The credential id to use for authentication."""

    model: str
    """The embedding model name (e.g. ``"text-embedding-3-small"``)."""

    parameters: dict
    """The embedding model parameters (e.g. ``{"dimensions": 1024}``)."""


class SessionConfig(BaseModel):
    """Session configuration — set at creation, updatable via PATCH."""

    workspace_id: str
    """The workspace id this session is bound to."""

    name: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        description="Display name for the session.",
    )
    """The session display name."""

    chat_model_config: ChatModelConfig | None = None
    """The chat model config. None means no model has been configured yet."""

    fallback_chat_model_config: ChatModelConfig | None = None
    """The fallback chat model config. Used as a backup when the primary
    model fails. None means no fallback configured."""

    tts_model_config: TTSModelConfig | None = None
    """The TTS model config. None means TTS is not enabled."""

    effective_capabilities: CapabilitySnapshot | None = None
    """User/division-specific ERPX capability snapshot for this session.

    ``None`` preserves compatibility for non-ERPX callers. ERPX always sends
    an explicit manifest, including an empty one for fail-closed sessions.
    """

    runtime_run_id: str | None = None
    """Trusted ERPX RunID for the currently executing chat request."""


class SessionRecord(_RecordBase):
    """The session record."""

    user_id: str
    """The user id."""

    agent_id: str | None = None
    """Persisted Agent id. ``None`` for session-native DirectModel."""

    runtime_subject_id: str | None = None
    """Immutable session runtime subject for DirectModel."""

    runtime_profile: RuntimeProfile | None = None
    """Discriminated runtime construction profile.

    Stored sessions created before DM-2 omit this field and are interpreted as
    Agent sessions from their existing ``agent_id``.
    """

    source: SessionSource = SessionSource.USER
    """The source that created this session."""

    source_schedule_id: str | None = None
    """The source schedule Id."""

    team_id: str | None = None
    """The team this session participates in, if any.

    Team membership is session-level: a user agent can lead multiple teams
    across different sessions, and each worker session belongs to exactly
    one team. ``None`` means the session is not part of any team.
    """

    config: SessionConfig
    """Session configuration (workspace, name, model)."""

    state: AgentState = Field(default_factory=AgentState)
    """Mutable runtime state, updated after each chat turn."""

    @model_validator(mode="after")
    def _validate_runtime_identity(self) -> "SessionRecord":
        profile = self.runtime_profile
        if profile is None:
            if not self.agent_id:
                raise ValueError(
                    "Legacy session without runtime_profile requires agent_id",
                )
            self.runtime_profile = AgentRuntimeProfile(agent_id=self.agent_id)
            return self

        if isinstance(profile, AgentRuntimeProfile):
            if self.agent_id != profile.agent_id:
                raise ValueError("Agent runtime profile does not match agent_id")
            if self.runtime_subject_id is not None:
                raise ValueError(
                    "Agent runtime session cannot have runtime_subject_id",
                )
            return self

        if isinstance(profile, DirectModelRuntimeProfile):
            if self.agent_id is not None:
                raise ValueError(
                    "DirectModel runtime session cannot reference agent_id",
                )
            subject_id = profile.base_capabilities.subject_id
            if self.runtime_subject_id != subject_id:
                raise ValueError(
                    "DirectModel runtime subject does not match base manifest",
                )
            return self

        raise ValueError("Unsupported runtime profile")

    @property
    def runtime_owner_id(self) -> str:
        """Return the persisted index/workspace owner for this session."""
        if self.agent_id:
            return self.agent_id
        if self.runtime_subject_id:
            return f"direct_model__{self.runtime_subject_id}"
        raise ValueError("Session runtime identity is incomplete")
