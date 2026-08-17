# -*- coding: utf-8 -*-
"""Token-window chunking for the complete normalized snapshot Markdown."""
from __future__ import annotations

import hashlib
import re

from ._models import KnowledgeChunk

_TOKEN_PATTERN = re.compile(r"\S+")


class MarkdownChunker:
    def __init__(self, max_tokens: int = 700, overlap_tokens: int = 80) -> None:
        if max_tokens <= 0 or overlap_tokens < 0 or overlap_tokens >= max_tokens:
            raise ValueError("Invalid chunk size or overlap.")
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens

    def chunk(self, markdown: str, *, snapshot_apk: str) -> list[KnowledgeChunk]:
        normalized = markdown.replace("\r\n", "\n").replace("\r", "\n").strip()
        matches = list(_TOKEN_PATTERN.finditer(normalized))
        if not matches:
            return []
        chunks = []
        start = 0
        step = self.max_tokens - self.overlap_tokens
        while start < len(matches):
            end = min(start + self.max_tokens, len(matches))
            char_start = matches[start].start()
            char_end = matches[end - 1].end()
            chunk_text = normalized[char_start:char_end].strip()
            chunks.append(KnowledgeChunk(
                object_apk=None,
                chunk_index=len(chunks),
                chunk_text=chunk_text,
                token_count=len(_TOKEN_PATTERN.findall(chunk_text)),
                content_hash=hashlib.sha256(chunk_text.encode("utf-8")).hexdigest().upper(),
                section_path="Markdown tổng",
                source_locator_json={
                    "snapshot_apk": snapshot_apk,
                    "source_type": "SNAPSHOT_MARKDOWN",
                },
            ))
            if end == len(matches):
                break
            start += step
        return chunks


ObjectChunker = MarkdownChunker
