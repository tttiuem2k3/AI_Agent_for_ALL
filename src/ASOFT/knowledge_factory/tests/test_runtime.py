from __future__ import annotations

import asyncio

import pytest

from ASOFT.knowledge_factory import KnowledgeFactorySettings
from ASOFT.knowledge_factory._embedding import create_embedding_model
from ASOFT.knowledge_factory._models import IndexJobStatus, PublishResponse
from ASOFT.knowledge_factory._runtime import KnowledgeFactoryRuntime


class FakeRepository:
    def __init__(self, response: PublishResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, str]] = []

    async def enqueue_publish(self, snapshot_apk: str, index_version: str) -> PublishResponse:
        self.calls.append((snapshot_apk, index_version))
        return self.response


class FakeWorker:
    def __init__(self) -> None:
        self.wake_count = 0

    def wake(self) -> None:
        self.wake_count += 1


class FakeEmbeddingModel:
    dimensions = 3

    async def __call__(self, inputs: list[str]):
        class Response:
            embeddings = [[float(index), 0.0, 1.0] for index, _ in enumerate(inputs)]
        return Response()


def _settings(**overrides):
    values = dict(
        enabled=True,
        sql_connection_string="Driver=x",
        api_key="secret",
        embedding_provider="openai_credential",
        embedding_model="text-embedding-3-small",
        embedding_dimensions=1536,
        embedding_api_key="sk-test",
        embedding_base_url=None,
        ollama_host=None,
        chunk_max_tokens=700,
        chunk_overlap_tokens=80,
        index_version="rag.v1",
        poll_interval_seconds=2.0,
        lease_seconds=120,
        max_concurrency=2,
        max_reclaim_retries=3,
        apply_migrations=True,
    )
    values.update(overrides)
    return KnowledgeFactorySettings(**values)


def test_embedding_factory_reuses_openai_provider() -> None:
    model = create_embedding_model(_settings())
    assert model.model == "text-embedding-3-small"
    assert model.dimensions == 1536


def test_embedding_factory_requires_api_key_for_remote_provider() -> None:
    with pytest.raises(RuntimeError, match="API key"):
        create_embedding_model(_settings(embedding_api_key=None))


def test_runtime_enqueues_and_wakes_worker() -> None:
    response = PublishResponse(
        snapshot_apk="SNAP-1",
        job_apk="JOB-1",
        status=IndexJobStatus.QUEUED,
        detail="Queued",
    )
    repository = FakeRepository(response)
    worker = FakeWorker()
    runtime = KnowledgeFactoryRuntime(
        settings=_settings(),
        repository=repository,
        worker=worker,
        embedding_model=FakeEmbeddingModel(),
    )

    result = asyncio.run(runtime.trigger("SNAP-1"))

    assert result == response
    assert repository.calls == [("SNAP-1", "rag.v1")]
    assert worker.wake_count == 1


def test_runtime_reports_not_configured_when_embedding_provider_missing() -> None:
    runtime = KnowledgeFactoryRuntime(
        settings=_settings(embedding_api_key=None),
        repository=FakeRepository(
            PublishResponse(
                snapshot_apk="SNAP-1",
                job_apk="JOB-1",
                status=IndexJobStatus.QUEUED,
                detail="Queued",
            )
        ),
    )

    with pytest.raises(Exception) as caught:
        asyncio.run(runtime.trigger("SNAP-1"))

    assert getattr(caught.value, "code", None) == "KNOWLEDGE_FACTORY_NOT_CONFIGURED"
