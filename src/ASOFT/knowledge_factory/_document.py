# -*- coding: utf-8 -*-
"""Deterministic KnowledgeDocument and Markdown construction."""
from __future__ import annotations

import json
from typing import Any

from jinja2 import Environment, StrictUndefined

from ._models import ActiveRelationRecord, ConvertedSourceMarkdown, KnowledgeDocument, KnowledgeObjectRecord

_TEMPLATE = """# {{ document.asset_title }}

## 1. Thông tin tri thức

- Tên tri thức: {{ document.asset_title }}
- AssetAPK: `{{ document.asset_apk }}`
- SnapshotAPK: `{{ document.snapshot_apk }}`
- Version: {{ document.snapshot_version_no }}
{% if document.asset_id %}- Mã tri thức: {{ document.asset_id }}
{% endif %}{% if document.asset_summary %}- Tóm tắt tri thức: {{ document.asset_summary }}
{% endif %}{% if document.primary_domain_apk %}- Danh mục/DomainAPK: `{{ document.primary_domain_apk }}`
{% endif %}{% if document.type_apk %}- Loại tri thức/TypeAPK: `{{ document.type_apk }}`
{% endif %}{% if document.department_id %}- Phòng ban: {{ document.department_id }}
{% endif %}{% if document.module_id %}- Module: {{ document.module_id }}
{% endif %}{% if document.screen_id %}- Màn hình: {{ document.screen_id }}
{% endif %}{% if document.tag_apks %}- TagAPK: {{ document.tag_apks | join(', ') }}
{% endif %}{% if document.approved_content_hash %}- ApprovedContentHash: `{{ document.approved_content_hash }}`
{% endif %}
{% if cross_asset_relation_rows %}### Quan hệ đến tri thức khác

{% for row in cross_asset_relation_rows %}- {{ row }}
{% endfor %}
{% endif %}## 2. Dữ liệu đối tượng và quan hệ

{% for item in document.objects %}### 2.{{ loop.index }}. {{ item.title }}

- Tên tri thức sở hữu: {{ document.asset_title }}
- Tiêu đề đối tượng: {{ item.title }}
{% if item.module_id %}- Module: {{ item.module_id }}
{% endif %}{% if item.screen_id %}- Màn hình: {{ item.screen_id }}
{% endif %}{% if item.metadata_json %}- Metadata: `{{ item.metadata_json | tojson_sorted }}`
{% endif %}
{% if object_relation_rows[item.apk] %}#### Mối quan hệ liên quan

{% for row in object_relation_rows[item.apk] %}- {{ row }}
{% endfor %}
{% endif %}{% if item.summary %}#### Tóm tắt

{{ item.summary }}

{% endif %}#### Nội dung chi tiết

{{ item.content }}

{% if item.source_locator_json %}#### Nguồn

`{{ item.source_locator_json | tojson_sorted }}`

{% endif %}{% endfor %}
{% if source_markdowns %}## 3. Tài liệu nguồn đã chuyển Markdown

{% for source in source_markdowns %}### 3.{{ loop.index }}. {{ source.source.source_file_name }}

- FileAPK: `{{ source.source.file_apk }}`
- Format: {{ source.format }}
{% if source.source.mime_type %}- MimeType: {{ source.source.mime_type }}
{% endif %}{% if source.source.source_content_hash %}- SourceContentHash: `{{ source.source.source_content_hash }}`
{% endif %}{% if source.warnings %}- Cảnh báo: {{ source.warnings | join(', ') }}
{% endif %}
{{ source.markdown | trim }}

{% endfor %}{% endif %}"""

class KnowledgeDocumentBuilder:
    def build(self, snapshot: dict[str, Any] | Any, objects: list[KnowledgeObjectRecord], relations: list[ActiveRelationRecord]) -> KnowledgeDocument:
        value = snapshot if isinstance(snapshot, dict) else snapshot.model_dump()
        return KnowledgeDocument(
            snapshot_apk=str(value["apk"]),
            division_id=str(value["division_id"]),
            asset_apk=str(value["asset_apk"]),
            asset_title=str(value["asset_title"]),
            snapshot_version_no=int(value["snapshot_version_no"]),
            asset_id=value.get("asset_id"),
            asset_summary=value.get("asset_summary"),
            primary_domain_apk=value.get("primary_domain_apk"),
            type_apk=value.get("type_apk"),
            department_id=value.get("department_id"),
            module_id=value.get("module_id"),
            screen_id=value.get("screen_id"),
            tag_apks=list(value.get("tag_apks") or []),
            approved_content_hash=value.get("approved_content_hash"),
            objects=sorted(objects, key=lambda item: (item.display_order, item.object_key)),
            relations=relations,
        )

class MarkdownRenderer:
    def __init__(self) -> None:
        environment = Environment(autoescape=False, undefined=StrictUndefined, keep_trailing_newline=True, trim_blocks=True, lstrip_blocks=True)
        environment.filters["tojson_sorted"] = lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self._template = environment.from_string(_TEMPLATE)

    def render(
        self,
        document: KnowledgeDocument,
        *,
        source_markdowns: list[ConvertedSourceMarkdown] | None = None,
    ) -> str:
        objects = {item.apk: item for item in document.objects}
        object_relation_rows = {item.apk: [] for item in document.objects}
        cross_asset_relation_rows = []
        for relation in document.relations:
            text = self._relation_text(relation, objects)
            if relation.source_object_apk in object_relation_rows:
                object_relation_rows[relation.source_object_apk].append(text)
            if relation.target_object_apk in object_relation_rows:
                object_relation_rows[relation.target_object_apk].append(text)
            if relation.target_asset_apk:
                cross_asset_relation_rows.append(text)
        return self._template.render(
            document=document,
            object_relation_rows=object_relation_rows,
            cross_asset_relation_rows=cross_asset_relation_rows,
            source_markdowns=source_markdowns or [],
        ).replace("\r\n", "\n").replace("\r", "\n").strip() + "\n"

    def _relation_text(self, relation: ActiveRelationRecord, objects: dict[str, KnowledgeObjectRecord]) -> str:
        source = objects.get(relation.source_object_apk)
        source_name = source.title if source is not None else relation.source_object_apk
        target_name = self._target_name(relation, objects)
        text = f"{source_name} --{relation.relation_type_id}--> {target_name}"
        if relation.condition_text:
            text += f"; Điều kiện: {relation.condition_text}"
        if relation.description:
            text += f"; Mô tả: {relation.description}"
        return text

    @staticmethod
    def _target_name(relation: ActiveRelationRecord, objects: dict[str, KnowledgeObjectRecord]) -> str:
        if relation.target_object_apk:
            target = objects.get(relation.target_object_apk)
            return target.title if target is not None else relation.target_object_apk
        if relation.target_asset_apk:
            asset = relation.target_asset_title or relation.target_asset_apk
            if relation.target_object_key:
                return f"Tri thức {asset} / Đối tượng {relation.target_object_key}"
            return f"Tri thức {asset}"
        if relation.target_object_key:
            return relation.target_object_key
        return "External"
