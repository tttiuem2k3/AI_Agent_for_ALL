# -*- coding: utf-8 -*-
"""The agent storage class."""
from typing import Literal

from pydantic import Field, BaseModel

from Common._utils._common import _generate_id
from ._base import _RecordBase
from Runtime.agent import ContextConfig, ReActConfig
from ._capability import CapabilityManifest


class AgentData(BaseModel):
    """The agent data model."""

    id: str = Field(
        description="Unique agent id",
        default_factory=_generate_id,
    )
    """The agent id."""

    name: str = Field(
        description="The name of the agent.",
        title="Name",
    )

    system_prompt: str = Field(
        default="You're a helpful assistant.",
        description="The system prompt for the agent.",
        title="System Prompt",
        # Hint for schema-driven UI renderers; see ``ContextConfig`` for
        # the same pattern on long-form prompts.
        json_schema_extra={"format": "textarea"},
    )

    context_config: ContextConfig = Field(
        description="The context config for the agent.",
        title="Context Config",
    )

    react_config: ReActConfig = Field(
        description="The react config for the agent.",
        title="React Config",
    )

    base_capabilities: CapabilityManifest | None = Field(
        default=None,
        description=(
            "ERPX Agent-level assignment/scope/runtime capability manifest. "
            "None preserves non-ERPX compatibility."
        ),
    )


class AgentRecord(_RecordBase):
    """The agent ORM model."""

    user_id: str
    """The user id"""

    source: Literal["user", "team"] = "user"
    """How this agent was created.

    - ``"user"``: created directly by the user (default). Can have multiple
      sessions and is listed in the user's regular agent list.
    - ``"team"``: spawned as a team worker by another agent's
      ``create_team`` / ``team_add_member`` tool. Has exactly one session.
      Team membership itself is session-level and stored on
      :class:`SessionRecord.team_id`.
    """

    data: AgentData
    """The agent data"""
