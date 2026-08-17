# -*- coding: utf-8 -*-
"""Internal contracts for the ASOFT Knowledge Factory."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class IndexJobStatus(str, Enum):
    QUEUED = "Queued"
    PROCESSING = "Processing"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


class SnapshotIndexRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    apk: str
    division_id: str
    asset_apk: str
    asset_title: str
    snapshot_version_no: int
    asset_id: str | None = None
    asset_summary: str | None = None
    primary_domain_apk: str | None = None
    type_apk: str | None = None
    department_id: str | None = None
    module_id: str | None = None
    screen_id: str | None = None
    tag_apks: list[str] = Field(default_factory=list)
    snapshot_status_id: str
    normalized_file_apk: str | None = None
    content_hash: str | None = None
    approved_content_hash: str | None = None
    successful_job_apk: str | None = None
    index_version: str | None = None


class KnowledgeObjectRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    apk: str
    object_key: str
    title: str
    content: str
    display_order: int
    parent_apk: str | None = None
    summary: str | None = None
    module_id: str | None = None
    screen_id: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    source_locator_json: dict[str, Any] = Field(default_factory=dict)


class ActiveRelationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    apk: str
    source_object_apk: str
    target_object_apk: str | None = None
    target_asset_apk: str | None = None
    target_asset_title: str | None = None
    target_object_key: str | None = None
    relation_type_id: str
    description: str | None = None
    condition_text: str | None = None


class KnowledgeDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    snapshot_apk: str
    division_id: str
    asset_title: str
    snapshot_version_no: int
    asset_apk: str = ""
    asset_id: str | None = None
    asset_summary: str | None = None
    primary_domain_apk: str | None = None
    type_apk: str | None = None
    department_id: str | None = None
    module_id: str | None = None
    screen_id: str | None = None
    tag_apks: list[str] = Field(default_factory=list)
    approved_content_hash: str | None = None
    objects: list[KnowledgeObjectRecord]
    relations: list[ActiveRelationRecord]


class KnowledgeChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")
    object_apk: str | None = None
    chunk_index: int
    chunk_text: str
    token_count: int
    content_hash: str
    section_path: str
    source_locator_json: dict[str, Any] = Field(default_factory=dict)


class SourceDocumentRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_apk: str
    source_ordinal: int
    source_file_name: str
    mime_type: str | None = None
    source_content_hash: str | None = None

class ConvertedSourceMarkdown(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: SourceDocumentRecord
    markdown: str
    format: str
    warnings: list[str] = Field(default_factory=list)

class NormalizedMarkdownFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    apk: str
    path: str
    attach_name: str
    file_size: int
    content_hash: str


class IndexJobRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    apk: str
    division_id: str
    snapshot_apk: str
    status: IndexJobStatus
    index_version: str
    approved_content_hash: str
    input_manifest_hash: str
    retry_count: int = 0
    progress_percent: int = 0
    lease_owner: str | None = None
    lease_expires_date: datetime | None = None


class PublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    snapshot_apk: str = Field(min_length=1, max_length=100)


class PublishResponse(BaseModel):
    snapshot_apk: str
    job_apk: str
    status: IndexJobStatus
    detail: str
