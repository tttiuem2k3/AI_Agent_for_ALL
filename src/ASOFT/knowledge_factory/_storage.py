# -*- coding: utf-8 -*-
"""Shared ERPX file storage for generated Knowledge Factory Markdown."""
from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path
import uuid

from ._errors import KnowledgeFactoryError
from ._models import IndexJobRecord, NormalizedMarkdownFile, SourceDocumentRecord


class KnowledgeFactoryStorage:
    def __init__(self, repository) -> None:
        self._repository = repository
        self._root: Path | None = None
        self._lock = asyncio.Lock()

    async def root(self) -> Path:
        if self._root is not None:
            return self._root
        async with self._lock:
            if self._root is None:
                web_path = await self._repository.get_web_physical_path()
                self._root = Path(web_path) / "Attached" / "Files"
        return self._root

    async def write_markdown(
        self,
        job: IndexJobRecord,
        markdown: str,
    ) -> NormalizedMarkdownFile:
        root = await self.root()
        data = (markdown.rstrip("\n") + "\n").encode("utf-8")
        content_hash = hashlib.sha256(data).hexdigest().upper()
        file_apk = str(uuid.uuid4()).upper()
        final_path = root / f"{file_apk}.md"
        temp_path = root / f".{file_apk}.{uuid.uuid4().hex}.tmp"
        await asyncio.to_thread(root.mkdir, parents=True, exist_ok=True)
        try:
            await asyncio.to_thread(self._write_atomic, temp_path, final_path, data)
        except Exception as exc:
            await asyncio.to_thread(self._safe_unlink, temp_path)
            raise KnowledgeFactoryError(
                "MARKDOWN_WRITE_FAILED",
                "The generated Markdown could not be written to shared storage.",
            ) from exc
        return NormalizedMarkdownFile(
            apk=file_apk,
            path=str(final_path),
            attach_name=f"knowledge-{job.snapshot_apk}.md",
            file_size=len(data),
            content_hash=content_hash,
        )

    async def read_source_document(self, source: SourceDocumentRecord) -> bytes:
        root = await self.root()
        suffix = Path(source.source_file_name).suffix
        candidates = [
            root / f"{source.file_apk}{suffix}",
            root / f"{source.file_apk.lower()}{suffix.lower()}",
            root / str(source.file_apk),
            root / source.source_file_name,
        ]
        for path in candidates:
            if path.exists():
                return await asyncio.to_thread(path.read_bytes)
        raise KnowledgeFactoryError(
            "SOURCE_DOCUMENT_NOT_FOUND",
            f"Source document was not found: {source.source_file_name}",
        )

    async def delete(self, file: NormalizedMarkdownFile) -> None:
        await asyncio.to_thread(self._safe_unlink, Path(file.path))

    @staticmethod
    def _write_atomic(temp_path: Path, final_path: Path, data: bytes) -> None:
        with temp_path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, final_path)

    @staticmethod
    def _safe_unlink(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            return
