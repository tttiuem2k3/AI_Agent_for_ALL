# -*- coding: utf-8 -*-
"""Application-scoped polling worker for ONT2210 indexing jobs."""
from __future__ import annotations

import asyncio
import os
import socket
import uuid

from _logging import logger

from ._chunking import MarkdownChunker
from ._config import KnowledgeFactorySettings
from Capabilities.document_conversion import DocumentConversionError

from ._document import KnowledgeDocumentBuilder, MarkdownRenderer
from ._document_conversion import KnowledgeFactorySourceConverter
from ._errors import KnowledgeFactoryError, LeaseLostError
from ._models import ConvertedSourceMarkdown, IndexJobRecord
from ._process_log import KnowledgeFactoryProcessLogger
from ._repository import KnowledgeFactoryRepository
from ._storage import KnowledgeFactoryStorage


def create_worker_id() -> str:
    host = socket.gethostname().replace(":", "_")[:40]
    return f"kf:{host}:{os.getpid()}:{uuid.uuid4().hex[:12]}"[:100]


class KnowledgeFactoryWorker:
    def __init__(
        self,
        settings: KnowledgeFactorySettings,
        repository: KnowledgeFactoryRepository,
        embedding_model,
        *,
        process_logger: KnowledgeFactoryProcessLogger | None = None,
        source_converter: KnowledgeFactorySourceConverter | None = None,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.embedding_model = embedding_model
        self.storage = KnowledgeFactoryStorage(repository)
        self.process_logger = process_logger or KnowledgeFactoryProcessLogger()
        self.source_converter = source_converter or KnowledgeFactorySourceConverter()
        self.worker_id = create_worker_id()
        self._stop = asyncio.Event()
        self._wake = asyncio.Event()
        self._loop_task: asyncio.Task | None = None
        self._jobs: set[asyncio.Task] = set()

    async def start(self) -> None:
        if self._loop_task is not None:
            return
        if not self.settings.enabled:
            logger.info("Knowledge Factory worker is disabled.")
            return
        self._stop.clear()
        self._loop_task = asyncio.create_task(self._run_loop(), name=f"knowledge-factory:{self.worker_id}")

    async def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._loop_task is not None:
            await self._loop_task
            self._loop_task = None
        for task in list(self._jobs):
            task.cancel()
        if self._jobs:
            await asyncio.gather(*self._jobs, return_exceptions=True)
        self._jobs.clear()

    def wake(self) -> None:
        self._wake.set()

    async def _run_loop(self) -> None:
        while not self._stop.is_set():
            self._drop_finished_tasks()
            available = self.settings.max_concurrency - len(self._jobs)
            claimed = False
            while available > 0 and not self._stop.is_set():
                job = await self.repository.claim_next(
                    self.worker_id,
                    self.settings.lease_seconds,
                    self.settings.max_reclaim_retries,
                )
                if job is None:
                    break
                claimed = True
                self._jobs.add(asyncio.create_task(self.process_job(job), name=f"knowledge-index:{job.apk}"))
                available -= 1
            if claimed:
                await asyncio.sleep(0)
                continue
            self._wake.clear()
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=self.settings.poll_interval_seconds)
            except TimeoutError:
                pass

    def _drop_finished_tasks(self) -> None:
        finished = {task for task in self._jobs if task.done()}
        self._jobs.difference_update(finished)
        for task in finished:
            try:
                task.result()
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("Unhandled Knowledge Factory job failure.")

    async def process_job(self, job: IndexJobRecord) -> None:
        run_id = self._start_process_log(job)
        try:
            await self.repository.heartbeat(job, self.worker_id, self.settings.lease_seconds, 15)
            snapshot, objects, relations = await self.repository.load_index_input(job)
            self._log_step(
                run_id,
                "Tải dữ liệu từ DB",
                input_data={"job": job.model_dump(mode="json")},
                output_data={
                    "snapshot": snapshot.model_dump(mode="json"),
                    "object_count": len(objects),
                    "objects": [item.model_dump(mode="json") for item in objects],
                    "relation_count": len(relations),
                    "relations": [item.model_dump(mode="json") for item in relations],
                },
            )
            document = KnowledgeDocumentBuilder().build(snapshot, objects, relations)
            self._log_step(
                run_id,
                "Gom dữ liệu tri thức",
                input_data={"object_count": len(objects), "relation_count": len(relations)},
                output_data={"document": document.model_dump(mode="json")},
            )
            source_markdowns = await self._convert_source_markdowns(job, run_id)
            markdown = MarkdownRenderer().render(document, source_markdowns=source_markdowns)
            self._log_step(
                run_id,
                "Tạo Markdown",
                input_data={
                    "snapshot_apk": document.snapshot_apk,
                    "object_count": len(document.objects),
                    "source_markdown_count": len(source_markdowns),
                },
                output_data={"character_count": len(markdown), "markdown": markdown},
            )
            chunks = MarkdownChunker(
                max_tokens=self.settings.chunk_max_tokens,
                overlap_tokens=self.settings.chunk_overlap_tokens,
            ).chunk(markdown, snapshot_apk=job.snapshot_apk)
            if not chunks:
                raise KnowledgeFactoryError("CHUNKS_EMPTY", "No chunks were produced for the approved snapshot.")
            self._log_step(
                run_id,
                "Cắt chunk",
                input_data={
                    "chunk_max_tokens": self.settings.chunk_max_tokens,
                    "chunk_overlap_tokens": self.settings.chunk_overlap_tokens,
                    "markdown_character_count": len(markdown),
                },
                output_data={
                    "chunk_count": len(chunks),
                    "total_tokens": sum(chunk.token_count for chunk in chunks),
                    "chunks": [chunk.model_dump(mode="json") for chunk in chunks],
                },
            )
            await self.repository.heartbeat(job, self.worker_id, self.settings.lease_seconds, 45)
            chunk_texts = [chunk.chunk_text for chunk in chunks]
            response = await self.embedding_model(chunk_texts)
            embeddings = [list(map(float, vector)) for vector in response.embeddings]
            self._log_step(
                run_id,
                "Tạo embedding",
                input_data={
                    "model": self.settings.embedding_model,
                    "chunk_count": len(chunk_texts),
                    "chunk_texts": chunk_texts,
                },
                output_data=self._embedding_log_output(embeddings),
            )
            await self.repository.heartbeat(job, self.worker_id, self.settings.lease_seconds, 80)
            markdown_file = await self.storage.write_markdown(job, markdown)
            self._log_step(
                run_id,
                "Lưu Markdown",
                input_data={"character_count": len(markdown)},
                output_data={"markdown_file": markdown_file.model_dump(mode="json")},
            )
            try:
                await self.repository.commit_success(
                    job,
                    self.worker_id,
                    markdown_file,
                    chunks,
                    embeddings,
                    self.settings.embedding_dimensions,
                )
            except Exception:
                await self.storage.delete(markdown_file)
                raise
            self._log_step(
                run_id,
                "Lưu vector",
                input_data={
                    "job_apk": job.apk,
                    "snapshot_apk": job.snapshot_apk,
                    "chunk_count": len(chunks),
                    "embedding_count": len(embeddings),
                    "embedding_dimensions": self.settings.embedding_dimensions,
                },
                output_data={"status": "Succeeded", "saved_vector_count": len(embeddings)},
            )
            self._finish_process_log(run_id, "Succeeded", {"chunk_count": len(chunks), "vector_count": len(embeddings)})
        except LeaseLostError:
            self._finish_process_log(run_id, "LeaseLost")
            raise
        except KnowledgeFactoryError as exc:
            self._finish_process_log(run_id, "Failed", {"error_code": exc.code, "message": exc.safe_message})
            await self.repository.fail_job(job, self.worker_id, exc.code, exc.safe_message)
        except Exception as exc:
            self._finish_process_log(run_id, "Failed", {"error_code": "INDEXING_FAILED", "message": str(exc)})
            await self.repository.fail_job(job, self.worker_id, "INDEXING_FAILED", str(exc))

    async def _convert_source_markdowns(
        self,
        job: IndexJobRecord,
        run_id: int | None,
    ) -> list[ConvertedSourceMarkdown]:
        if not hasattr(self.repository, "load_source_documents"):
            return []
        sources = await self.repository.load_source_documents(job)
        if not sources:
            self._log_step(
                run_id,
                "Chuyển tài liệu nguồn sang Markdown",
                input_data={"snapshot_apk": job.snapshot_apk},
                output_data={"source_count": 0, "converted_count": 0},
            )
            return []
        converted_sources = []
        for source in sources:
            try:
                content = await self.storage.read_source_document(source)
                converted = await self.source_converter.convert_source(
                    content,
                    filename=source.source_file_name,
                    mime_type=source.mime_type,
                    include_structure=False,
                    include_assets=False,
                )
            except DocumentConversionError as exc:
                raise KnowledgeFactoryError(
                    "SOURCE_DOCUMENT_CONVERSION_FAILED",
                    f"Source document conversion failed for {source.source_file_name}: {exc.safe_message}",
                ) from exc
            converted_sources.append(
                ConvertedSourceMarkdown(
                    source=source,
                    markdown=converted.markdown,
                    format=converted.format.value,
                    warnings=list(converted.warnings),
                )
            )
        self._log_step(
            run_id,
            "Chuyển tài liệu nguồn sang Markdown",
            input_data={
                "snapshot_apk": job.snapshot_apk,
                "sources": [source.model_dump(mode="json") for source in sources],
            },
            output_data={
                "converted_count": len(converted_sources),
                "files": [
                    {
                        "source_file_name": item.source.source_file_name,
                        "format": item.format,
                        "markdown_character_count": len(item.markdown),
                        "warnings": item.warnings,
                    }
                    for item in converted_sources
                ],
            },
        )
        return converted_sources

    def _start_process_log(self, job: IndexJobRecord) -> int | None:
        try:
            return self.process_logger.start_run(job_apk=job.apk, snapshot_apk=job.snapshot_apk)
        except Exception:
            logger.exception("Could not start Knowledge Factory process log.")
            return None

    def _log_step(
        self,
        run_id: int | None,
        title: str,
        *,
        input_data: dict | None = None,
        output_data: dict | None = None,
    ) -> None:
        if run_id is None:
            return
        try:
            self.process_logger.step(run_id, title, input_data=input_data, output_data=output_data)
        except Exception:
            logger.exception("Could not write Knowledge Factory process log step: %s", title)

    def _finish_process_log(self, run_id: int | None, status: str, output_data: dict | None = None) -> None:
        if run_id is None:
            return
        try:
            self.process_logger.finish(run_id, status=status, output_data=output_data)
        except Exception:
            logger.exception("Could not finish Knowledge Factory process log.")

    @staticmethod
    def _embedding_log_output(embeddings: list[list[float]]) -> dict:
        return {
            "embedding_count": len(embeddings),
            "dimensions": [len(vector) for vector in embeddings],
            "vector_preview": [vector[:8] for vector in embeddings],
            "note": "Chỉ ghi 8 giá trị đầu của mỗi vector để tránh file log quá lớn.",
        }

