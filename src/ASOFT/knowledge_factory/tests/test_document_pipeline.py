from __future__ import annotations
import pytest
from ASOFT.knowledge_factory import ActiveRelationRecord, KnowledgeDocumentBuilder, KnowledgeFactorySettings, KnowledgeObjectRecord, MarkdownRenderer, ObjectChunker, SQLServerVectorCodec


def _document(content: str = "Nội dung ngắn."):
    return KnowledgeDocumentBuilder().build(
        {"apk": "SNAP-1", "division_id": "AS", "asset_title": "KB", "snapshot_version_no": 1},
        [KnowledgeObjectRecord(apk="OBJ-1", object_key="policy", title="Chính sách", content=content, display_order=1, summary="Tóm tắt", source_locator_json={"sourceOrdinal": 1})], [],
    )


def test_markdown_contains_objects_and_relations():
    document = KnowledgeDocumentBuilder().build(
        {"apk": "SNAP-1", "division_id": "AS", "asset_title": "Quy trình", "snapshot_version_no": 3},
        [KnowledgeObjectRecord(apk="A", object_key="a", title="Tạo", content="Tạo dữ liệu", display_order=1), KnowledgeObjectRecord(apk="B", object_key="b", title="Duyệt", content="Duyệt dữ liệu", display_order=2)],
        [ActiveRelationRecord(apk="R", source_object_apk="A", target_object_apk="B", relation_type_id="Next")],
    )
    markdown = MarkdownRenderer().render(document)
    assert "# Quy trình" in markdown
    assert "## 1. Tạo" in markdown
    assert "Tạo --Next--> Duyệt" in markdown


def test_chunker_keeps_metadata_and_splits_long_objects():
    chunks = ObjectChunker(max_tokens=12, overlap_tokens=2).chunk(_document(" ".join(f"từ{i}" for i in range(25))))
    assert len(chunks) > 1
    assert [item.chunk_index for item in chunks] == list(range(len(chunks)))
    assert chunks[0].source_locator_json == {"sourceOrdinal": 1}
    assert "## Chính sách" in chunks[0].section_path


def test_vector_codec_validates_dimension():
    assert SQLServerVectorCodec.to_sql_literal([0.1, -0.2, 3], dimensions=3) == "[0.1,-0.2,3.0]"
    with pytest.raises(ValueError, match="dimension"):
        SQLServerVectorCodec.to_sql_literal([0.1], dimensions=2)


def test_settings_load_embedding_configuration(monkeypatch):
    monkeypatch.setenv("ASOFT_AI_KF_ENABLED", "true")
    monkeypatch.setenv("ASOFT_ERPX_KM_SQL_CONNECTION_STRING", "Driver=x")
    monkeypatch.setenv("ASOFT_AI_KF_EMBEDDING_DIMENSIONS", "1536")
    settings = KnowledgeFactorySettings.from_env()
    assert settings.embedding_model == "text-embedding-3-small"
    assert settings.embedding_dimensions == 1536


def test_settings_enable_knowledge_factory_by_default(monkeypatch):
    monkeypatch.delenv("ASOFT_AI_KF_ENABLED", raising=False)
    monkeypatch.setenv("ASOFT_ERPX_KM_SQL_CONNECTION_STRING", "Driver=x")
    monkeypatch.setenv("ASOFT_AI_KF_EMBEDDING_DIMENSIONS", "1536")

    settings = KnowledgeFactorySettings.from_env()

    assert settings.enabled is True
