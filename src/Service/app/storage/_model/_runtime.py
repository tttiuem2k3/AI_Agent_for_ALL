# -*- coding: utf-8 -*-
"""Persisted runtime profiles for Agent and session-native DirectModel."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from Runtime.agent import ContextConfig, ReActConfig
from ._capability import CapabilityManifestV2


class AgentRuntimeProfile(BaseModel):
    """Reference to a persisted Agent configuration."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["agent"] = "agent"
    agent_id: str = Field(min_length=1, max_length=100)


class WorkflowRuntimeProfile(BaseModel):
    """An Agent session driven by an ON AI Workflow node, not by a person.

    Identical to :class:`AgentRuntimeProfile` in what it references — the same
    persisted Agent, the same v1 base capabilities on the ``AgentRecord`` — and
    different in exactly one respect: the turn is unattended, so the framework
    must attach *nothing* the graph author did not choose.  ``get_toolkit``
    reads this profile to skip the planner, background, schedule, team and MCP
    blocks it otherwise attaches unconditionally.

    Base capabilities deliberately are **not** duplicated here.  An Agent
    session already carries them on its ``AgentRecord`` and ``_effective_tool_names``
    already validates the effective manifest against that record; storing a
    second copy on the profile would create two sources of truth for the same
    fact.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["workflow"] = "workflow"
    profile_version: Literal["1"] = "1"
    agent_id: str = Field(min_length=1, max_length=100)


class DirectModelRuntimeProfile(BaseModel):
    """Server-owned recipe for constructing an ephemeral runtime Agent."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["direct_model"] = "direct_model"
    profile_version: Literal["1"] = "1"
    system_prompt_profile: Literal["direct-chat-v1"] = "direct-chat-v1"
    context_config: ContextConfig = Field(default_factory=ContextConfig)
    react_config: ReActConfig = Field(default_factory=ReActConfig)
    base_capabilities: CapabilityManifestV2

    @model_validator(mode="after")
    def _validate_subject(self) -> "DirectModelRuntimeProfile":
        if self.base_capabilities.subject_type != "DirectModel":
            raise ValueError(
                "DirectModel runtime requires a DirectModel capability subject",
            )
        return self


RuntimeProfile = Annotated[
    AgentRuntimeProfile | WorkflowRuntimeProfile | DirectModelRuntimeProfile,
    Field(discriminator="kind"),
]
