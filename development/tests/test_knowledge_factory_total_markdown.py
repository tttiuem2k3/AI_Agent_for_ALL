from __future__ import annotations

from ASOFT.knowledge_factory._chunking import MarkdownChunker
from ASOFT.knowledge_factory._document import KnowledgeDocumentBuilder, MarkdownRenderer
from ASOFT.knowledge_factory._models import (
    ActiveRelationRecord,
    ConvertedSourceMarkdown,
    KnowledgeObjectRecord,
    SnapshotIndexRecord,
    SourceDocumentRecord,
)


def test_total_markdown_orders_metadata_objects_then_source_files():
    snapshot = SnapshotIndexRecord(
        apk="SNAP",
        division_id="AS",
        asset_apk="ASSET",
        asset_id="KB-001",
        asset_title="Quy trình mua thiết bị",
        asset_summary="Tri thức hướng dẫn mua thiết bị.",
        primary_domain_apk="DOMAIN-PURCHASE",
        type_apk="TYPE-PROCESS",
        department_id="IT",
        module_id="PO",
        screen_id="POF2000",
        tag_apks=["TAG-LAPTOP", "TAG-DUYET"],
        snapshot_version_no=2,
        snapshot_status_id="Approved",
    )
    first = KnowledgeObjectRecord(
        apk="OBJ-1",
        object_key="request",
        title="Tạo đề nghị",
        summary="Người dùng tạo đề nghị mua.",
        content="Nhập thiết bị, số lượng và lý do mua.",
        display_order=1,
    )
    second = KnowledgeObjectRecord(
        apk="OBJ-2",
        object_key="approve",
        title="Duyệt đề nghị",
        summary="Trưởng bộ phận duyệt đề nghị.",
        content="Kiểm tra ngân sách và xác nhận phê duyệt.",
        display_order=2,
    )
    relations = [
        ActiveRelationRecord(
            apk="REL-1",
            source_object_apk="OBJ-1",
            target_object_apk="OBJ-2",
            relation_type_id="NextStep",
            description="Sau khi tạo đề nghị thì chuyển sang duyệt.",
        ),
        ActiveRelationRecord(
            apk="REL-2",
            source_object_apk="OBJ-2",
            target_asset_apk="ASSET-BUDGET",
            target_object_key="budget-check",
            relation_type_id="ReferencesKnowledge",
            description="Có liên quan tri thức kiểm tra ngân sách.",
        ),
    ]
    source_markdown = ConvertedSourceMarkdown(
        source=SourceDocumentRecord(file_apk="FILE-1", source_ordinal=1, source_file_name="mau.xlsx"),
        markdown="# File mẫu\n\nNội dung file mẫu đã chuyển Markdown.",
        format="excel",
    )
    document = KnowledgeDocumentBuilder().build(snapshot, [second, first], relations)

    markdown = MarkdownRenderer().render(document, source_markdowns=[source_markdown])

    metadata_index = markdown.index("## 1. Thông tin tri thức")
    object_index = markdown.index("## 2. Dữ liệu đối tượng và quan hệ")
    file_index = markdown.index("## 3. Tài liệu nguồn đã chuyển Markdown")
    assert metadata_index < object_index < file_index
    assert "Tên tri thức: Quy trình mua thiết bị" in markdown
    assert "TagAPK: TAG-LAPTOP, TAG-DUYET" in markdown
    assert "Quan hệ đến tri thức khác" in markdown
    assert markdown.index("### 2.1. Tạo đề nghị") < markdown.index("### 2.2. Duyệt đề nghị")
    assert "Tên tri thức sở hữu: Quy trình mua thiết bị" in markdown
    assert "NextStep" in markdown
    assert "ReferencesKnowledge" in markdown
    assert "Nội dung file mẫu đã chuyển Markdown" in markdown


def test_markdown_chunker_splits_total_markdown_not_per_object():
    markdown = "# Tri thức\n\n" + " ".join(f"token{i}" for i in range(120))

    chunks = MarkdownChunker(max_tokens=50, overlap_tokens=10).chunk(markdown, snapshot_apk="SNAP")

    assert len(chunks) == 3
    assert all(chunk.object_apk is None for chunk in chunks)
    assert [chunk.chunk_index for chunk in chunks] == [0, 1, 2]
    assert all(chunk.section_path == "Markdown tổng" for chunk in chunks)
    assert chunks[0].chunk_text.startswith("# Tri thức")
