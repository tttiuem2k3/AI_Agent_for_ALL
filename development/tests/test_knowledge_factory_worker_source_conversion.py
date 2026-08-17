from __future__ import annotations

import asyncio

from ASOFT.knowledge_factory import KnowledgeFactorySettings
from ASOFT.knowledge_factory._models import IndexJobRecord, IndexJobStatus, SourceDocumentRecord
from ASOFT.knowledge_factory._worker import KnowledgeFactoryWorker
from Capabilities.document_conversion import ConvertedDocument, DocumentFormat


class FakeRepository:
    async def load_source_documents(self, job):
        return [
            SourceDocumentRecord(
                file_apk="FILE-1",
                source_ordinal=1,
                source_file_name="guide.docx",
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                source_content_hash="HASH",
            )
        ]


class FakeStorage:
    async def read_source_document(self, source):
        assert source.file_apk == "FILE-1"
        return b"DOCX-BYTES"


class FakeSourceConverter:
    async def convert_source(self, content, **kwargs):
        assert content == b"DOCX-BYTES"
        assert kwargs["filename"] == "guide.docx"
        return ConvertedDocument(
            format=DocumentFormat.DOCX,
            markdown="# Converted\n\nMarkdown tốt.\n",
        )


class UnusedEmbedding:
    async def __call__(self, inputs):
        raise AssertionError("Embedding is not used in this test")


def test_worker_converts_snapshot_source_documents_to_markdown(tmp_path):
    settings = KnowledgeFactorySettings(
        enabled=True,
        sql_connection_string="Driver=x",
        api_key=None,
        embedding_provider="openai_credential",
        embedding_model="text-embedding-3-small",
        embedding_dimensions=3,
        embedding_api_key="sk",
        embedding_base_url=None,
        ollama_host=None,
        chunk_max_tokens=50,
        chunk_overlap_tokens=5,
        index_version="rag.v1",
        poll_interval_seconds=2,
        lease_seconds=120,
        max_concurrency=1,
        max_reclaim_retries=3,
        apply_migrations=True,
    )
    worker = KnowledgeFactoryWorker(
        settings,
        FakeRepository(),
        UnusedEmbedding(),
        source_converter=FakeSourceConverter(),
    )
    worker.storage = FakeStorage()
    job = IndexJobRecord(
        apk="JOB",
        division_id="AS",
        snapshot_apk="SNAP",
        status=IndexJobStatus.PROCESSING,
        index_version="rag.v1",
        approved_content_hash="",
        input_manifest_hash="",
    )

    converted = asyncio.run(worker._convert_source_markdowns(job, None))

    assert len(converted) == 1
    assert converted[0].source.source_file_name == "guide.docx"
    assert converted[0].format == "docx"
    assert "Markdown tốt" in converted[0].markdown
