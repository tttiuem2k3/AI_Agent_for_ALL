# -*- coding: utf-8 -*-
"""Translate native parse objects into engine-neutral ASOFT structures."""
from __future__ import annotations

from typing import Any

from ._models import DocumentAsset, StructuredDocument


def convert_native_document(document: Any) -> StructuredDocument:
    assets = tuple(_asset(item) for item in document.assets)
    return StructuredDocument(
        blocks=tuple(_block(item) for item in document.blocks),
        notes=tuple(_note(item) for item in document.notes),
        assets=assets,
    )


def _asset(value: Any) -> DocumentAsset:
    return DocumentAsset(
        id=int(value.id),
        media_type=str(value.media_type),
        origin_part=str(value.origin_part),
        data=bytes(value.data),
    )


def _style(value: Any | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "bold": bool(value.bold),
        "italic": bool(value.italic),
        "strike": bool(value.strike),
        "code": bool(value.code),
    }


def _inline(value: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"kind": str(value.kind)}
    for name in ("text", "alt", "anchor", "note_id"):
        item = getattr(value, name, None)
        if item is not None:
            result[name] = item
    if getattr(value, "style", None) is not None:
        result["style"] = _style(value.style)
    if getattr(value, "content", None) is not None:
        result["content"] = [_inline(item) for item in value.content]
    target = getattr(value, "target", None)
    if target is not None:
        result["target"] = {"kind": str(target.kind), "value": str(target.value)}
    source = getattr(value, "source", None)
    if source is not None:
        result["source"] = {
            "kind": str(source.kind),
            "url": getattr(source, "url", None),
            "asset_id": getattr(source, "asset_id", None),
        }
    return result


def _list(value: Any) -> dict[str, Any]:
    return {
        "marker": str(value.marker),
        "start": int(value.start),
        "items": [
            {
                "blocks": [_block(block) for block in item.blocks],
                "checked": item.checked,
                "marker_label": item.marker_label,
            }
            for item in value.items
        ],
    }


def _cell(value: Any) -> dict[str, Any]:
    return {
        "blocks": [_block(block) for block in value.blocks],
        "col_span": int(value.col_span),
        "row_span": int(value.row_span),
    }


def _cell_slot(value: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"kind": str(value.kind)}
    if value.cell is not None:
        result["cell"] = _cell(value.cell)
    if value.origin_row is not None:
        result["origin_row"] = int(value.origin_row)
    if value.origin_col is not None:
        result["origin_col"] = int(value.origin_col)
    return result


def _table(value: Any) -> dict[str, Any]:
    return {
        "kind": str(value.kind),
        "header_rows": int(value.header_rows),
        "grid": [[_cell_slot(slot) for slot in row] for row in value.grid],
    }


def _note(value: Any) -> dict[str, Any]:
    return {
        "id": str(value.id),
        "kind": str(value.kind),
        "blocks": [_block(block) for block in value.blocks],
    }


def _block(value: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"kind": str(value.kind)}
    for name in ("level", "anchor", "lang", "text"):
        item = getattr(value, name, None)
        if item is not None:
            result[name] = item
    if getattr(value, "content", None) is not None:
        result["content"] = [_inline(item) for item in value.content]
    if getattr(value, "list", None) is not None:
        result["list"] = _list(value.list)
    if getattr(value, "table", None) is not None:
        result["table"] = _table(value.table)
    if getattr(value, "blocks", None) is not None:
        result["blocks"] = [_block(item) for item in value.blocks]
    return result
