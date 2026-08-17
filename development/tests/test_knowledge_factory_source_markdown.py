from __future__ import annotations

import asyncio

from ASOFT.knowledge_factory._document import KnowledgeDocumentBuilder, MarkdownRenderer
from ASOFT.knowledge_factory._document_conversion import KnowledgeFactorySourceConverter
from ASOFT.knowledge_factory._models import (
    ConvertedSourceMarkdown,
    KnowledgeObjectRecord,
    SnapshotIndexRecord,
    SourceDocumentRecord,
)
from Capabilities.document_conversion import ConvertedDocument, DocumentFormat


class FakeConverter:
    async def convert(self, content, *, filename=None, mime_type=None, format=None, options=None):
        assert content == b"DOCX-BYTES"
        assert filename == "guide.docx"
        return ConvertedDocument(
            format=DocumentFormat.DOCX,
            markdown="# File Markdown\n\nNội dung từ file docx đã convert.\n",
        )


def test_source_converter_markdown_can_be_appended_to_knowledge_markdown():
    source = SourceDocumentRecord(
        file_apk="FILE-1",
        source_ordinal=1,
        source_file_name="guide.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        source_content_hash="HASH",
    )
    converted = asyncio.run(
        KnowledgeFactorySourceConverter(FakeConverter()).convert_source(
            b"DOCX-BYTES",
            filename=source.source_file_name,
            mime_type=source.mime_type,
        )
    )
    source_markdown = ConvertedSourceMarkdown(
        source=source,
        markdown=converted.markdown,
        format=converted.format.value,
        warnings=list(converted.warnings),
    )
    snapshot = SnapshotIndexRecord(
        apk="SNAP",
        division_id="AS",
        asset_apk="ASSET",
        asset_title="Tri thức cài đặt",
        snapshot_version_no=1,
        snapshot_status_id="Approved",
    )
    document = KnowledgeDocumentBuilder().build(
        snapshot,
        [KnowledgeObjectRecord(apk="OBJ", object_key="obj", title="Bước xử lý", content="Nội dung đã chuẩn hóa.", display_order=1)],
        [],
    )

    markdown = MarkdownRenderer().render(document, source_markdowns=[source_markdown])

    assert "## 3. Tài liệu nguồn đã chuyển Markdown" in markdown
    assert "guide.docx" in markdown
    assert "Nội dung từ file docx đã convert." in markdown
    assert "### 2.1. Bước xử lý" in markdown
