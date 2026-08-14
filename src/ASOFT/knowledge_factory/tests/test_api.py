from __future__ import annotations

from fastapi.testclient import TestClient

from ASOFT.knowledge_factory import IndexJobStatus, KnowledgeFactorySettings, PublishResponse
from ASOFT.knowledge_factory._api import create_knowledge_factory_app


class FakeRuntime:
    def __init__(self) -> None:
        self.settings = KnowledgeFactorySettings(
            enabled=True, sql_connection_string="Driver=x", api_key="secret",
            embedding_provider="openai_credential", embedding_model="text-embedding-3-small", embedding_dimensions=3,
            embedding_api_key="sk", embedding_base_url=None, ollama_host=None,
            chunk_max_tokens=50, chunk_overlap_tokens=5, index_version="rag.v1",
            poll_interval_seconds=2, lease_seconds=120, max_concurrency=1, max_reclaim_retries=3, apply_migrations=True,
        )
        self.received: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

    async def trigger(self, snapshot_apk: str) -> PublishResponse:
        self.received.append(snapshot_apk)
        return PublishResponse(snapshot_apk=snapshot_apk, job_apk="JOB", status=IndexJobStatus.QUEUED, detail="Queued")


def test_publish_api_accepts_snapshot_signal_and_checks_api_key():
    runtime = FakeRuntime()
    with TestClient(create_knowledge_factory_app(runtime)) as client:
        unauthorized = client.post("/asoft/knowledge-factory/publish", json={"snapshot_apk": "SNAP"})
        response = client.post(
            "/asoft/knowledge-factory/publish",
            headers={"api-key": "secret"},
            json={"snapshot_apk": "SNAP"},
        )

    assert unauthorized.status_code == 401
    assert response.status_code == 202
    assert response.json()["job_apk"] == "JOB"
    assert runtime.received == ["SNAP"]
