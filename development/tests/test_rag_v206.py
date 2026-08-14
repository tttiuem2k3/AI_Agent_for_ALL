# -*- coding: utf-8 -*-

import asyncio
import builtins

import pytest


def test_rag_symbols_import_without_optional_backends() -> None:
    from Capabilities import rag

    assert rag.WordParser.supported_extensions() == [".docx"]
    assert ".xlsx" in rag.ExcelParser.supported_extensions()
    assert hasattr(rag, "VectorStoreBase")


def test_word_parser_dependency_error_is_lazy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from Capabilities.rag import WordParser

    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "docx":
            raise ImportError("missing python-docx")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    with pytest.raises(ImportError, match="python-docx"):
        asyncio.run(WordParser().parse(b"not-docx", "bad.docx"))


def test_v206_vector_store_adapters_are_exported_and_lazy() -> None:
    from Capabilities import rag

    stores = [
        rag.MilvusLiteStore(uri="test.db"),
        rag.MongoDBVectorStore(uri="mongodb://localhost", database="test"),
        rag.ElasticsearchVectorStore(hosts="http://localhost:9200"),
    ]

    assert all(store is not None for store in stores)


def test_milvus_dependency_is_loaded_only_when_client_is_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from Capabilities.rag import MilvusLiteStore

    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "pymilvus":
            raise ImportError("missing pymilvus")
        return real_import(name, *args, **kwargs)

    store = MilvusLiteStore(uri="test.db")
    monkeypatch.setattr(builtins, "__import__", guarded_import)

    with pytest.raises(ImportError, match="vdb-milvus"):
        store.get_client()


def test_vector_store_contract_includes_document_listing() -> None:
    from Capabilities.rag import VectorStoreBase

    assert "list_documents" in VectorStoreBase.__abstractmethods__
