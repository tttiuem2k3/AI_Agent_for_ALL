from __future__ import annotations

import asyncio

from ASOFT.knowledge_factory import KnowledgeFactorySettings
from ASOFT.knowledge_factory._models import ActiveRelationRecord, IndexJobRecord, IndexJobStatus, KnowledgeObjectRecord, NormalizedMarkdownFile, SnapshotIndexRecord
from ASOFT.knowledge_factory._worker import KnowledgeFactoryWorker


class FakeRepository:
    def __init__(self) -> None:
        self.committed = None
        self.progress: list[int] = []

    async def heartbeat(self, job, worker_id, lease_seconds, progress):
        self.progress.append(progress)

    async def load_index_input(self, job):
        return (
            SnapshotIndexRecord(apk="SNAP", division_id="AS", asset_apk="ASSET", asset_title="KB", snapshot_version_no=1, snapshot_status_id="Approved"),
            [KnowledgeObjectRecord(apk="OBJ", object_key="obj", title="Bước 1", content="Nội dung xử lý", display_order=1)],
            [ActiveRelationRecord(apk="REL", source_object_apk="OBJ", target_object_key="external", relation_type_id="References")],
        )

    async def commit_success(self, job, worker_id, markdown_file, chunks, embeddings, dimensions):
        self.committed = (markdown_file, chunks, embeddings, dimensions)

    async def fail_job(self, job, worker_id, code, message):
        raise AssertionError((code, message))


class FakeEmbedding:
    async def __call__(self, inputs):
        class Response:
            embeddings = [[0.1, 0.2, 0.3] for _ in inputs]
        return Response()


def test_worker_processes_job_to_embeddings():
    settings = KnowledgeFactorySettings(
        enabled=True, sql_connection_string="Driver=x", api_key=None,
        embedding_provider="openai_credential", embedding_model="text-embedding-3-small", embedding_dimensions=3,
        embedding_api_key="sk", embedding_base_url=None, ollama_host=None,
        chunk_max_tokens=50, chunk_overlap_tokens=5, index_version="rag.v1",
        poll_interval_seconds=2, lease_seconds=120, max_concurrency=1, max_reclaim_retries=3, apply_migrations=True,
    )
    repository = FakeRepository()
    worker = KnowledgeFactoryWorker(settings, repository, FakeEmbedding())
    class FakeStorage:
        async def write_markdown(self, job, markdown):
            assert "# KB" in markdown
            return NormalizedMarkdownFile(apk="FILE", path="", attach_name="file.md", file_size=1, content_hash="HASH")
        async def delete(self, file):
            raise AssertionError("delete should not be called")
    worker.storage = FakeStorage()
    job = IndexJobRecord(apk="JOB", division_id="AS", snapshot_apk="SNAP", status=IndexJobStatus.PROCESSING, index_version="rag.v1", approved_content_hash="", input_manifest_hash="")

    asyncio.run(worker.process_job(job))

    assert repository.progress == [15, 45, 80]
    markdown_file, chunks, embeddings, dimensions = repository.committed
    assert markdown_file.content_hash == "HASH"
    assert dimensions == 3
    assert len(chunks) == len(embeddings) == 1
    assert "Nội dung xử lý" in chunks[0].chunk_text



