# -*- coding: utf-8 -*-
"""ASOFT Knowledge Factory: approved ERPX knowledge to RAG vectors."""
from ._api import create_knowledge_factory_app, create_knowledge_factory_router
from ._chunking import MarkdownChunker, ObjectChunker
from ._config import KnowledgeFactorySettings
from ._document import KnowledgeDocumentBuilder, MarkdownRenderer
from ._document_conversion import KnowledgeFactorySourceConverter
from ._embedding import create_embedding_model
from ._errors import KnowledgeFactoryError, LeaseLostError
from ._models import ActiveRelationRecord, IndexJobRecord, IndexJobStatus, KnowledgeChunk, KnowledgeDocument, KnowledgeObjectRecord, NormalizedMarkdownFile, PublishRequest, PublishResponse, SnapshotIndexRecord
from ._runtime import KnowledgeFactoryRuntime
from ._vector import SQLServerVectorCodec

__all__ = [
    "ActiveRelationRecord", "IndexJobRecord", "IndexJobStatus", "KnowledgeChunk",
    "KnowledgeDocument", "KnowledgeDocumentBuilder", "KnowledgeFactoryError",
    "KnowledgeFactoryRuntime", "KnowledgeFactorySettings", "KnowledgeFactorySourceConverter", "KnowledgeObjectRecord",
    "LeaseLostError", "MarkdownChunker", "MarkdownRenderer", "NormalizedMarkdownFile", "ObjectChunker",
    "PublishRequest", "PublishResponse", "SQLServerVectorCodec", "SnapshotIndexRecord",
    "create_embedding_model", "create_knowledge_factory_app", "create_knowledge_factory_router",
]
