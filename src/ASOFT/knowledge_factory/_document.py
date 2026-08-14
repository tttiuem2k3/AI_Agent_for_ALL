# -*- coding: utf-8 -*-
"""Deterministic KnowledgeDocument and Markdown construction."""
from __future__ import annotations

import json
from typing import Any

from jinja2 import Environment, StrictUndefined

from ._models import ActiveRelationRecord, KnowledgeDocument, KnowledgeObjectRecord

_TEMPLATE = """# {{ document.asset_title }}

- SnapshotAPK: `{{ document.snapshot_apk }}`
- Version: {{ document.snapshot_version_no }}
{% if document.approved_content_hash %}- ApprovedContentHash: `{{ document.approved_content_hash }}`
{% endif %}
{% for item in document.objects %}
## {{ loop.index }}. {{ item.title }}

{% if item.summary %}**Tóm tắt:** {{ item.summary }}

{% endif %}{{ item.content }}

{% if item.source_locator_json %}**Nguồn:** `{{ item.source_locator_json | tojson_sorted }}`

{% endif %}{% endfor %}
{% if relation_rows %}### Quan hệ tri thức

{% for row in relation_rows %}- {{ row }}
{% endfor %}{% endif %}"""


class KnowledgeDocumentBuilder:
    def build(self, snapshot: dict[str, Any] | Any, objects: list[KnowledgeObjectRecord], relations: list[ActiveRelationRecord]) -> KnowledgeDocument:
        value = snapshot if isinstance(snapshot, dict) else snapshot.model_dump()
        return KnowledgeDocument(
            snapshot_apk=str(value["apk"]), division_id=str(value["division_id"]),
            asset_title=str(value["asset_title"]), snapshot_version_no=int(value["snapshot_version_no"]),
            approved_content_hash=value.get("approved_content_hash"),
            objects=sorted(objects, key=lambda item: (item.display_order, item.object_key)), relations=relations,
        )


class MarkdownRenderer:
    def __init__(self) -> None:
        environment = Environment(autoescape=False, undefined=StrictUndefined, keep_trailing_newline=True, trim_blocks=True, lstrip_blocks=True)
        environment.filters["tojson_sorted"] = lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self._template = environment.from_string(_TEMPLATE)

    def render(self, document: KnowledgeDocument) -> str:
        titles = {item.apk: item.title for item in document.objects}
        rows = []
        for relation in document.relations:
            source = titles.get(relation.source_object_apk, relation.source_object_apk)
            target = titles.get(relation.target_object_apk or "", relation.target_object_key or relation.target_asset_apk or "External")
            text = f"{source} --{relation.relation_type_id}--> {target}"
            if relation.condition_text:
                text += f" (Điều kiện: {relation.condition_text})"
            if relation.description:
                text += f": {relation.description}"
            rows.append(text)
        return self._template.render(document=document, relation_rows=rows).replace("\r\n", "\n").replace("\r", "\n").strip() + "\n"
