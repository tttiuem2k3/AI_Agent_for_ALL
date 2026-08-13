# -*- coding: utf-8 -*-
"""Persisted ERPX capability contracts for Agent and session binding."""
import hashlib
import json
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


def compute_capability_manifest_v2_hash(payload: dict) -> str:
    """Hash a manifest-v2 payload that does not contain its ``hash`` field."""
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ToolCapability(BaseModel):
    """One model-visible tool resolved by ERPX."""

    model_config = ConfigDict(extra="forbid")

    tool_id: str = Field(min_length=1, max_length=40)
    function_name: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    tool_type: str = Field(min_length=1, max_length=30)
    tool_group: str = Field(min_length=1, max_length=50)
    description_for_llm: str = Field(min_length=1)
    input_schema: dict
    output_schema: dict | None = None
    is_read_only: bool
    require_approval: bool

    executor_type: str = Field(default="PythonRuntime", min_length=1, max_length=30)
    """Which ON execution plane owns this Tool.

    Descriptive only on the Python side: Python never dispatches by it, it just
    carries ERPX's decision so the factory knows which wrapper to build.
    """

    is_external_execution: bool = False

    @field_validator("input_schema")
    @classmethod
    def _validate_input_schema(cls, value: dict) -> dict:
        if (
            value.get("type") != "object"
            or not isinstance(value.get("properties"), dict)
        ):
            raise ValueError("input_schema must be an object JSON Schema")
        return value


class SkillCapability(BaseModel):
    """One catalog Skill assigned to the ERPX Agent."""

    model_config = ConfigDict(extra="forbid")

    skill_id: str = Field(min_length=1, max_length=40)
    description: str = Field(min_length=1, max_length=2000)
    skill_markdown: str = Field(min_length=1, max_length=1_000_000)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def _validate_skill(self) -> "SkillCapability":
        skill_id = self.skill_id
        if (
            not all(character in "abcdefghijklmnopqrstuvwxyz0123456789-"
                    for character in skill_id)
            or skill_id.startswith("-")
            or skill_id.endswith("-")
            or "--" in skill_id
        ):
            raise ValueError("skill_id must be a lowercase runtime slug")

        actual_hash = hashlib.sha256(
            self.skill_markdown.encode("utf-8"),
        ).hexdigest()
        if actual_hash != self.content_hash:
            raise ValueError("skill_markdown does not match content_hash")
        return self


class CapabilityManifest(BaseModel):
    """Versioned capability snapshot supplied by authenticated ERPX SERVICES."""

    model_config = ConfigDict(extra="forbid")

    manifest_version: Literal["1.0"] = "1.0"
    agent_apk: str | None = None
    agent_id: str = ""
    user_id: str | None = None
    division_id: str = Field(default="", max_length=50)
    capability_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    tools: list[ToolCapability] = Field(default_factory=list)
    skills: list[SkillCapability] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_unique_tools(self) -> "CapabilityManifest":
        tool_ids = [tool.tool_id for tool in self.tools]
        function_names = [tool.function_name for tool in self.tools]
        if len(tool_ids) != len(set(tool_ids)):
            raise ValueError("capability manifest contains duplicate ToolID")
        if len(function_names) != len(set(function_names)):
            raise ValueError(
                "capability manifest contains duplicate FunctionName",
            )
        skill_ids = [skill.skill_id for skill in self.skills]
        if len(skill_ids) != len(set(skill_ids)):
            raise ValueError("capability manifest contains duplicate SkillID")
        return self


class CapabilityManifestV2(BaseModel):
    """Subject-oriented capability snapshot for session-native runtimes.

    Version 2 deliberately has no Agent-specific fields.  The authenticated
    service caller supplies a stable runtime subject, while Python recomputes
    the canonical hash before accepting the snapshot.
    """

    model_config = ConfigDict(extra="forbid")

    manifest_version: Literal["2"] = "2"
    subject_type: Literal["Agent", "DirectModel"]
    subject_id: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    user_id: str = Field(min_length=1, max_length=100)
    division_id: str = Field(min_length=1, max_length=50)
    hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    tools: list[ToolCapability] = Field(default_factory=list, max_length=32)
    skills: list[SkillCapability] = Field(default_factory=list, max_length=16)

    def canonical_payload(self) -> dict:
        """Return the exact payload covered by :attr:`hash`."""
        return self.model_dump(
            mode="json",
            exclude={"hash"},
        )

    def computed_hash(self) -> str:
        """Compute the SHA-256 hash of the canonical manifest payload."""
        return compute_capability_manifest_v2_hash(
            self.canonical_payload(),
        )

    @model_validator(mode="after")
    def _validate_manifest(self) -> "CapabilityManifestV2":
        tool_ids = [tool.tool_id for tool in self.tools]
        function_names = [tool.function_name for tool in self.tools]
        skill_ids = [skill.skill_id for skill in self.skills]
        if len(tool_ids) != len(set(tool_ids)):
            raise ValueError("capability manifest contains duplicate ToolID")
        if len(function_names) != len(set(function_names)):
            raise ValueError(
                "capability manifest contains duplicate FunctionName",
            )
        if len(skill_ids) != len(set(skill_ids)):
            raise ValueError("capability manifest contains duplicate SkillID")

        canonical_size = len(
            json.dumps(
                self.canonical_payload(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8"),
        )
        if canonical_size > 1_048_576:
            raise ValueError("capability manifest exceeds 1 MiB")
        if self.hash != self.computed_hash():
            raise ValueError("capability manifest hash does not match payload")
        return self


CapabilitySnapshot = CapabilityManifest | CapabilityManifestV2
