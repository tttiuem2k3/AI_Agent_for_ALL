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
    AgentRuntimeProfile | DirectModelRuntimeProfile,
    Field(discriminator="kind"),
]
