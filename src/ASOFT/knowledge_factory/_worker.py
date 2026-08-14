# -*- coding: utf-8 -*-
"""Application-scoped polling worker for ONT2210 indexing jobs."""
from __future__ import annotations

import asyncio
import os
import socket
import uuid

from _logging import logger

from ._chunking import ObjectChunker
from ._config import KnowledgeFactorySettings
from ._document import KnowledgeDocumentBuilder, MarkdownRenderer
from ._errors import KnowledgeFactoryError, LeaseLostError
from ._models import IndexJobRecord
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
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.embedding_model = embedding_model
        self.storage = KnowledgeFactoryStorage(repository)
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
        try:
            await self.repository.heartbeat(job, self.worker_id, self.settings.lease_seconds, 15)
            snapshot, objects, relations = await self.repository.load_index_input(job)
            document = KnowledgeDocumentBuilder().build(snapshot, objects, relations)
            markdown = MarkdownRenderer().render(document)
            chunks = ObjectChunker(
                max_tokens=self.settings.chunk_max_tokens,
                overlap_tokens=self.settings.chunk_overlap_tokens,
            ).chunk(document)
            if not chunks:
                raise KnowledgeFactoryError("CHUNKS_EMPTY", "No chunks were produced for the approved snapshot.")
            await self.repository.heartbeat(job, self.worker_id, self.settings.lease_seconds, 45)
            response = await self.embedding_model([chunk.chunk_text for chunk in chunks])
            embeddings = [list(map(float, vector)) for vector in response.embeddings]
            await self.repository.heartbeat(job, self.worker_id, self.settings.lease_seconds, 80)
            markdown_file = await self.storage.write_markdown(job, markdown)
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
        except LeaseLostError:
            raise
        except KnowledgeFactoryError as exc:
            await self.repository.fail_job(job, self.worker_id, exc.code, exc.safe_message)
        except Exception as exc:
            await self.repository.fail_job(job, self.worker_id, "INDEXING_FAILED", str(exc))

