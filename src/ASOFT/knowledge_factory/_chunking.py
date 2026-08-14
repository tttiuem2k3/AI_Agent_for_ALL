# -*- coding: utf-8 -*-
"""Object-aware chunking for approved ERPX knowledge."""
from __future__ import annotations

import hashlib
import re

from ._models import KnowledgeChunk, KnowledgeDocument, KnowledgeObjectRecord

_TOKEN_PATTERN = re.compile(r"\S+")


class ObjectChunker:
    def __init__(self, max_tokens: int = 700, overlap_tokens: int = 80) -> None:
        if max_tokens <= 0 or overlap_tokens < 0 or overlap_tokens >= max_tokens:
            raise ValueError("Invalid chunk size or overlap.")
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens

    def chunk(self, document: KnowledgeDocument) -> list[KnowledgeChunk]:
        chunks = []
        objects = {item.apk: item for item in document.objects}
        for item in document.objects:
            prefix = f"# {document.asset_title}\n\n## {item.title}\n\n"
            body = "\n\n".join(part for part in ([f"Tóm tắt: {item.summary}"] if item.summary else []) + [item.content]).strip()
            words = _TOKEN_PATTERN.findall(body)
            for index, window in enumerate(self._windows(words)):
                text = prefix + " ".join(window)
                chunks.append(KnowledgeChunk(
                    object_apk=item.apk, chunk_index=index, chunk_text=text,
                    token_count=len(_TOKEN_PATTERN.findall(text)),
                    content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest().upper(),
                    section_path=self._section_path(item.apk, objects),
                    source_locator_json=item.source_locator_json,
                ))
        return chunks

    def _windows(self, words: list[str]) -> list[list[str]]:
        if len(words) <= self.max_tokens:
            return [words or [""]]
        step = self.max_tokens - self.overlap_tokens
        return [words[start:start + self.max_tokens] for start in range(0, len(words), step)]

    @staticmethod
    def _section_path(object_apk: str, objects: dict[str, KnowledgeObjectRecord]) -> str:
        titles, visited = [], set()
        current = objects.get(object_apk)
        while current is not None and current.apk not in visited:
            visited.add(current.apk)
            titles.append(current.title)
            current = objects.get(current.parent_apk) if current.parent_apk else None
        return " / ".join(f"## {title}" for title in reversed(titles))
