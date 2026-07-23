# -*- coding: utf-8 -*-
"""Generate the ERPX/ASOFT AI Services connection and storage design document."""

from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


OUTPUT = Path("Services_Python_Thong_tin_ket_noi_va_luu_tru_hoan_chinh.docx")


def shade(cell, fill: str) -> None:
    """Set a table-cell background color."""
    properties = cell._tc.get_or_add_tcPr()
    element = OxmlElement("w:shd")
    element.set(qn("w:fill"), fill)
    properties.append(element)


def set_cell(cell, value: str, *, header: bool = False) -> None:
    """Write a consistently styled table cell."""
    cell.text = ""
    run = cell.paragraphs[0].add_run(str(value))
    run.bold = header
    run.font.name = "Arial"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
    run.font.size = Pt(8.5 if not header else 9)
    if header:
        run.font.color.rgb = RGBColor(255, 255, 255)
        shade(cell, "245B78")
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def add_table(
    doc: Document,
    headers: list[str],
    rows: list[tuple[str, ...]],
) -> None:
    """Add a banded table."""
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for index, header in enumerate(headers):
        set_cell(table.rows[0].cells[index], header, header=True)
    for row_index, row in enumerate(rows):
        cells = table.add_row().cells
        for index, value in enumerate(row):
            set_cell(cells[index], value)
            if row_index % 2:
                shade(cells[index], "EAF2F5")
    doc.add_paragraph()


def add_bullets(doc: Document, items: list[str]) -> None:
    """Add compact bullet paragraphs."""
    for item in items:
        paragraph = doc.add_paragraph(style="List Bullet")
        paragraph.paragraph_format.space_after = Pt(2)
        paragraph.add_run(item)


def add_numbers(doc: Document, items: list[str]) -> None:
    """Add compact numbered paragraphs."""
    for item in items:
        paragraph = doc.add_paragraph(style="List Number")
        paragraph.paragraph_format.space_after = Pt(2)
        paragraph.add_run(item)


def add_code(doc: Document, text: str) -> None:
    """Add a monospace architecture/code block."""
    table = doc.add_table(rows=1, cols=1)
    table.style = "Table Grid"
    cell = table.cell(0, 0)
    shade(cell, "F3F6F8")
    cell.text = ""
    run = cell.paragraphs[0].add_run(text)
    run.font.name = "Consolas"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Consolas")
    run.font.size = Pt(8.5)
    doc.add_paragraph()


def build_document() -> Document:
    """Create the complete design document."""
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(0.7)
    section.bottom_margin = Inches(0.7)
    section.left_margin = Inches(0.75)
    section.right_margin = Inches(0.75)

    doc.styles["Normal"].font.name = "Arial"
    doc.styles["Normal"]._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
    doc.styles["Normal"].font.size = Pt(10.5)
    for name, size, color in [
        ("Title", 22, "17365D"),
        ("Heading 1", 16, "17365D"),
        ("Heading 2", 13, "245B78"),
        ("Heading 3", 11, "2F6B7C"),
    ]:
        style = doc.styles[name]
        style.font.name = "Arial"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
        style.font.size = Pt(size)
        style.font.color.rgb = RGBColor.from_string(color)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_before = Pt(70)
    run = title.add_run("THIẾT KẾ KẾT NỐI VÀ LƯU TRỮ DỮ LIỆU")
    run.bold = True
    run.font.name = "Arial"
    run.font.size = Pt(22)
    run.font.color.rgb = RGBColor(23, 54, 93)
    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run("AI SERVICE (PYTHON/ASOFT AI Services) CHO ERPX")
    run.bold = True
    run.font.name = "Arial"
    run.font.size = Pt(18)
    run.font.color.rgb = RGBColor(36, 91, 120)
    note = doc.add_paragraph()
    note.alignment = WD_ALIGN_PARAGRAPH.CENTER
    note.add_run(
        "Kiến trúc lựa chọn: ERPX Business Service quản lý SQL Server 2025",
    ).italic = True
    add_table(
        doc,
        ["Thuộc tính", "Giá trị"],
        [
            ("Nền tảng AI", "ASOFT AI Services 2.0.3 / FastAPI / Python 3.11+"),
            ("Nguồn dữ liệu chính", "ERPX Business Service + SQL Server 2025"),
            (
                "Vai trò Python Service",
                "Điều phối agent, model, tool, MCP, middleware và streaming",
            ),
            ("Ngày cập nhật", "30/06/2026"),
        ],
    )
    doc.add_page_break()

    doc.add_heading("1. Mục tiêu và phạm vi", level=1)
    doc.add_paragraph(
        "Tài liệu mô tả kiến trúc kết nối và lưu trữ khi phát triển mã nguồn "
        "ASOFT AI Services thành AI Service (Python) phục vụ ERPX. ERPX Business "
        "Service là nguồn dữ liệu duy nhất và kết nối trực tiếp SQL Server "
        "2025. AI Service nhận dữ liệu cần thiết, đồng bộ ngữ cảnh runtime, "
        "thực thi AI và gửi kết quả/trạng thái về ERPX.",
    )
    add_bullets(
        doc,
        [
            "Chuẩn hóa trách nhiệm giữa ERPX Business Service và AI Service.",
            "Phân loại dữ liệu bảng SQL, cột VECTOR, workspace và MessageBus.",
            "Định nghĩa kết nối, đồng bộ, retry, idempotency, bảo mật và audit.",
            "Định nghĩa lộ trình thay RedisStorage mà không nhầm với MessageBus.",
        ],
    )

    doc.add_heading("2. Quyết định kiến trúc", level=1)
    doc.add_paragraph(
        "Phương án được chọn: ERPX Business Service quản lý database và là "
        "source of truth. AI Service không truy cập trực tiếp SQL Server.",
    )
    add_code(
        doc,
        "ERPX Client\n"
        "    ↓ HTTPS\n"
        "ERPX Business Service ───────────→ SQL Server 2025\n"
        "    ↓ gọi AI / nhận kết quả            ├─ Bảng quan hệ + JSON\n"
        "AI Service (Python/ASOFT AI Services)         └─ Cột VECTOR\n"
        "    ├─ ERPXStorageAdapter ─ REST/gRPC → ERPX Internal API\n"
        "    ├─ Agent runtime / Model / Tool / MCP\n"
        "    ├─ SSE event stream\n"
        "    └─ Workspace runtime tạm thời",
    )
    add_bullets(
        doc,
        [
            "ERPX quản lý schema, transaction, tenant, phân quyền, credential và audit.",
            "AI Service triển khai ERPXStorageAdapter theo StorageBase.",
            "Adapter chủ động gọi ERPX khi ASOFT AI Services cần dữ liệu; ERPX không phải đẩy liên tục.",
            "Đọc theo runtime bundle và cache trong phạm vi một lượt chạy AI.",
            "Workspace local chỉ là runtime/cache, không phải nguồn dữ liệu chính.",
        ],
    )

    doc.add_heading("3. Trách nhiệm các thành phần", level=1)
    add_table(
        doc,
        ["Thành phần", "Trách nhiệm", "Không chịu trách nhiệm"],
        [
            (
                "ERPX Business Service",
                "Public API, user/tenant, authorization, SQL, transaction, audit, file metadata.",
                "Không chạy agent/model loop.",
            ),
            (
                "AI Service / ASOFT AI Services",
                "Agent runtime, model, tool/MCP, HITL, team, schedule AI, SSE và đồng bộ state.",
                "Không sở hữu database nghiệp vụ.",
            ),
            (
                "SQL Server 2025",
                "Record quan hệ, JSON cấu hình, lịch sử, audit, middleware và vector.",
                "Không thay thế event bus/workspace.",
            ),
            (
                "Workspace runtime",
                "Skill, MCP runtime config, file input/output và offload.",
                "Không lưu record/credential chính.",
            ),
            (
                "MessageBus",
                "Event, SSE replay, inbox, wakeup, queue và distributed lock.",
                "Không thay thế storage bền vững.",
            ),
        ],
    )

    doc.add_heading("4. Kết nối hệ thống", level=1)
    doc.add_heading("4.1 ERPX gọi AI Service", level=2)
    add_bullets(
        doc,
        [
            "ERPX gọi AI Service qua HTTPS REST; SSE dùng cho event realtime.",
            "Truyền tenant_id, user_id, agent_id, session_id, correlation_id và input.",
            "Xác thực service-to-service bằng OAuth2/JWT nội bộ hoặc mTLS.",
            "Không tin X-User-ID do client tự gửi trong môi trường production.",
        ],
    )
    doc.add_heading("4.2 AI Service gọi ERPX", level=2)
    add_table(
        doc,
        ["Nội dung", "Khuyến nghị"],
        [
            ("Giao thức", "REST/JSON async ban đầu; gRPC khi cần batch/tải lớn."),
            ("Phiên bản", "Đường dẫn /internal/ai/v1 và schema_version trong payload."),
            ("Timeout/retry", "Timeout theo nghiệp vụ, exponential backoff có giới hạn."),
            ("Theo dõi", "Correlation-Id/Trace-Id xuyên ERPX, AI, model và tool."),
            ("Transaction", "Không giữ transaction SQL trong thời gian chờ model."),
        ],
    )
    doc.add_heading("4.3 Model và tool nghiệp vụ", level=2)
    add_bullets(
        doc,
        [
            "AI Service gọi model provider qua Credential adapter của ASOFT AI Services.",
            "Nghiệp vụ ERPX được cung cấp qua MCP Server hoặc custom tool.",
            "Tool ghi dữ liệu phải kiểm tra tenant/quyền, audit, idempotency và HITL.",
        ],
    )

    doc.add_heading("5. API nội bộ đề xuất", level=1)
    add_table(
        doc,
        ["API", "Mục đích", "Dữ liệu"],
        [
            (
                "GET /internal/ai/v1/runtime-bundles/{sessionId}",
                "Tải dữ liệu cho một lượt chạy.",
                "Agent, Session, CredentialRef, model, state, messages, manifest.",
            ),
            (
                "PUT /internal/ai/v1/sessions/{id}/state",
                "Ghi state/checkpoint.",
                "StateJson, RowVersion.",
            ),
            (
                "POST /internal/ai/v1/sessions/{id}/messages:batch",
                "Ghi message theo batch.",
                "Messages[], IdempotencyKey.",
            ),
            (
                "GET /internal/ai/v1/workspaces/{id}/manifest",
                "Lấy manifest đồng bộ.",
                "Version, checksum, file URLs.",
            ),
            (
                "GET/POST /internal/ai/v1/files",
                "Tải lên/tải xuống file.",
                "Metadata, checksum, binary/signed URL.",
            ),
            (
                "POST /internal/ai/v1/memories:search",
                "Tìm middleware/knowledge.",
                "Embedding, filter, topK.",
            ),
            (
                "POST /internal/ai/v1/memories",
                "Ghi middleware.",
                "Content, embedding, metadata, scope.",
            ),
        ],
    )
    doc.add_heading("5.1 Runtime bundle mẫu", level=2)
    add_code(
        doc,
        '{\n'
        '  "schema_version": "1.0",\n'
        '  "tenant_id": "tenant-001", "user_id": "user-001",\n'
        '  "agent": {"id": "a-001", "name": "ERPX_Assistant"},\n'
        '  "session": {"id": "s-001", "workspace_id": "w-001", "state_version": 12},\n'
        '  "model": {"provider_type": "openai_credential", "model": "gpt-4.1"},\n'
        '  "credential_ref": "cred-001", "messages": [],\n'
        '  "workspace_manifest_version": "v8"\n'
        '}',
    )

    doc.add_heading("6. Dữ liệu lưu trên SQL Server 2025", level=1)
    doc.add_heading("6.1 Bảng quan hệ và JSON", level=2)
    add_table(
        doc,
        ["Bảng", "Trường chính", "Mục đích"],
        [
            (
                "AI_Credentials",
                "CredentialId, TenantId, ProviderType, Name, SecretEncrypted, BaseUrl, ConfigJson, RowVersion",
                "Credential và endpoint model.",
            ),
            (
                "AI_Agents",
                "AgentId, TenantId, Name, SystemPrompt, ContextConfigJson, ReactConfigJson, RowVersion",
                "Cấu hình agent.",
            ),
            (
                "AI_Sessions",
                "SessionId, AgentId, WorkspaceId, CredentialId, ModelName, ParametersJson, StateJson, RowVersion",
                "Liên kết runtime.",
            ),
            (
                "AI_Messages",
                "MessageId, SessionId, SequenceNo, Role, Name, ContentJson, MetadataJson, TokenUsageJson",
                "Hội thoại/tool blocks.",
            ),
            (
                "AI_Schedules / AI_ScheduleRuns",
                "ScheduleId, AgentId, Cron, ConfigJson, RunId, SessionId, Status",
                "Lịch và lịch sử chạy.",
            ),
            (
                "AI_Teams / AI_TeamMembers",
                "TeamId, LeaderSessionId, AgentId, SessionId, Role, Status",
                "Team và sub-agent.",
            ),
            (
                "AI_Skills",
                "SkillId, TenantId, Name, Description, MarkdownContent, Version, Checksum",
                "Nguồn chính của SKILL.md.",
            ),
            (
                "AI_McpConfigs",
                "McpId, WorkspaceId, Name, TransportType, UrlOrCommand, SecretEncrypted, ConfigJson",
                "Nguồn chính MCP.",
            ),
            (
                "AI_Workspaces / AI_Files",
                "WorkspaceId, ManifestVersion, FileId, StorageUri, MimeType, Size, Checksum",
                "Metadata workspace/file.",
            ),
            (
                "AI_AuditLogs",
                "AuditId, TenantId, UserId, Action, EntityType, EntityId, CorrelationId, DataJson",
                "Audit và truy vết.",
            ),
        ],
    )
    doc.add_heading("6.2 Bảng có cột VECTOR", level=2)
    add_table(
        doc,
        ["Nhóm", "Trường thường", "Cột vector", "Mục đích"],
        [
            (
                "Long-term middleware",
                "MemoryId, TenantId, UserId, AgentId, Content, MetadataJson",
                "Embedding VECTOR(n)",
                "Tìm ký ức tương đồng.",
            ),
            (
                "Knowledge chunks",
                "ChunkId, DocumentId, Content, Page/Section, MetadataJson",
                "Embedding VECTOR(n)",
                "RAG/tìm đoạn tài liệu.",
            ),
            (
                "Message embedding (tùy chọn)",
                "MessageId, SessionId, Content",
                "Embedding VECTOR(n)",
                "Tìm message quan trọng.",
            ),
            (
                "Skill embedding (tùy chọn)",
                "SkillId, Name, Description",
                "Embedding VECTOR(n)",
                "Tìm skill phù hợp.",
            ),
        ],
    )
    add_bullets(
        doc,
        [
            "Dữ liệu chính xác/quan hệ lưu bảng thường; VECTOR chỉ dùng tìm theo ngữ nghĩa.",
            "Luôn lưu nội dung gốc và metadata cùng embedding.",
            "Dimensions phải khớp embedding model; SQL Server 2025 hỗ trợ tối đa 1.998 chiều.",
            "Kiểm chứng vector index theo edition/build trước production.",
        ],
    )

    doc.add_heading("7. Workspace và file runtime", level=1)
    add_code(
        doc,
        "workspaces/{agent_id}/\n"
        "├── .mcp\n"
        "├── skills/\n"
        "│   ├── .skills\n"
        "│   └── <skill-name>/SKILL.md\n"
        "├── data/\n"
        "└── sessions/{session_id}/\n"
        "    ├── context.jsonl\n"
        "    └── tool_result-*.txt",
    )
    add_table(
        doc,
        ["Dữ liệu", "Nguồn chính", "Bản runtime"],
        [
            ("Skill", "SQL: AI_Skills/resources", "skills/<name>/SKILL.md"),
            ("MCP", "SQL: AI_McpConfigs", ".mcp/runtime config"),
            ("File đầu vào", "ERPX file service/object storage", "data/"),
            (
                "Context/tool result",
                "Workspace tạm; upload nếu cần lưu lâu",
                "sessions/{id}/",
            ),
            (
                "File kết quả",
                "ERPX file service + SQL metadata",
                "Tạo local rồi upload.",
            ),
        ],
    )
    doc.add_paragraph("WorkspaceSyncService thực hiện:")
    add_numbers(
        doc,
        [
            "Nhận workspace manifest/version từ runtime bundle.",
            "So sánh version/checksum với cache local.",
            "Tải skill, MCP config và file thay đổi.",
            "Tạo workspace trước khi dựng agent runtime.",
            "Upload file kết quả và ghi metadata về ERPX.",
            "Dọn workspace theo TTL sau khi bảo đảm đồng bộ thành công.",
        ],
    )

    doc.add_heading("8. Đồng bộ dữ liệu trong tiến trình AI", level=1)
    add_bullets(
        doc,
        [
            "ERPX/SQL là source of truth; AI Service không giữ database bền vững riêng.",
            "Dùng runtime bundle để giảm round-trip.",
            "Ghi message/state theo batch/checkpoint, không ghi theo từng token SSE.",
            "Dùng RowVersion/ETag chống ghi đè và Idempotency-Key chống ghi trùng.",
            "Mọi request có TenantId, UserId, CorrelationId và SchemaVersion.",
        ],
    )
    doc.add_heading("8.1 Luồng chat", level=2)
    add_code(
        doc,
        "1. ERPX bảo đảm Agent/Session đã tồn tại trong SQL.\n"
        "2. ERPX gọi AI Service POST /chat.\n"
        "3. ERPXStorageAdapter tải runtime bundle.\n"
        "4. WorkspaceSyncService đồng bộ skill/MCP/file.\n"
        "5. ASOFT AI Services dựng model + toolkit + middleware + agent runtime.\n"
        "6. Agent chạy ReAct và stream event qua SSE.\n"
        "7. Agent gọi MCP/custom tool khi cần nghiệp vụ ERPX.\n"
        "8. Adapter ghi message/state theo batch/checkpoint.\n"
        "9. ERPX commit SQL và trả RowVersion mới.\n"
        "10. AI Service upload file, giải phóng lock và kết thúc run.",
    )
    doc.add_heading("8.2 Lỗi và khôi phục", level=2)
    add_table(
        doc,
        ["Tình huống", "Xử lý"],
        [
            ("Storage API timeout", "Retry backoff có giới hạn; circuit breaker."),
            (
                "Mất response sau khi ghi",
                "Gửi lại cùng Idempotency-Key; ERPX trả kết quả cũ.",
            ),
            (
                "RowVersion conflict",
                "Tải state mới, merge theo policy hoặc kết thúc conflict.",
            ),
            (
                "Upload file lỗi",
                "Giữ local theo TTL, retry queue, chưa đánh dấu completed.",
            ),
            (
                "AI Service chết giữa run",
                "Run/checkpoint trong SQL để phát hiện stale và phục hồi.",
            ),
            (
                "ERPX không khả dụng",
                "Không chạy mới bằng dữ liệu stale ngoài policy.",
            ),
        ],
    )

    doc.add_heading("9. Redis và lộ trình thay thế", level=1)
    doc.add_paragraph(
        "Source hiện tại dùng RedisStorage cho Credential, Agent, Session, "
        "Message, State, Schedule và Team. Phần này sẽ được thay bằng "
        "ERPXStorageAdapter gọi ERPX Business Service/SQL Server 2025.",
    )
    add_table(
        doc,
        ["Hiện tại", "Sau chuyển đổi"],
        [
            (
                "RedisStorage: record/state/message",
                "ERPXStorageAdapter → ERPX API → SQL Server 2025.",
            ),
            (
                "InMemoryMessageBus",
                "Có thể giữ khi AI Service chạy một process.",
            ),
            (
                "RedisMessageBus",
                "Có thể vẫn cần khi chạy nhiều instance cho event/inbox/lock.",
            ),
            (
                "Workspace filesystem",
                "Vẫn là runtime/cache; nguồn chính chuyển về ERPX.",
            ),
            (
                "Mem0/Qdrant",
                "Thay bằng middleware adapter dùng SQL VECTOR nếu lựa chọn.",
            ),
        ],
    )
    add_bullets(
        doc,
        [
            "Thay RedisStorage không đồng nghĩa MessageBus tự động biến mất.",
            "SQL Server không nên làm pub/sub hoặc token-streaming bus.",
            "Nếu bỏ Redis hoàn toàn: dùng InMemoryMessageBus cho một instance hoặc triển khai broker adapter khác.",
        ],
    )

    doc.add_heading("10. Bảo mật", level=1)
    add_bullets(
        doc,
        [
            "Không truyền model API key ra client; secret được mã hóa tại ERPX.",
            "AI Service chỉ nhận secret khi dựng model client và tuyệt đối không log.",
            "Mọi dữ liệu phải scope theo TenantId và authorization đã xác thực.",
            "Dùng TLS, mTLS/JWT nội bộ, rotate key và network isolation.",
            "Tool ghi ERPX phải authorization lại, audit và HITL khi nhạy cảm.",
            "Mask credential, dữ liệu cá nhân và nội dung nhạy cảm trong log/error.",
            "Backup/restore, retention và encryption at rest cho SQL/file storage.",
        ],
    )

    doc.add_heading("11. Phi chức năng và vận hành", level=1)
    add_table(
        doc,
        ["Yêu cầu", "Thiết kế"],
        [
            (
                "Hiệu năng",
                "Runtime bundle, cache trong một run, batch write, connection pool.",
            ),
            (
                "Khả dụng",
                "Health/readiness cho ERPX API, SQL, model, bus và workspace.",
            ),
            (
                "Quan sát",
                "OpenTelemetry, structured log, model/tool/sync latency.",
            ),
            (
                "Scale",
                "AI Service stateless về record; distributed lock khi scale ngang.",
            ),
            (
                "Nhất quán",
                "RowVersion + transaction ERPX + idempotency.",
            ),
            (
                "Giới hạn",
                "File/context/token/max iterations/tool/model timeout.",
            ),
        ],
    )

    doc.add_heading("12. Kế hoạch triển khai", level=1)
    add_numbers(
        doc,
        [
            "Chuẩn hóa ID, TenantId, UserId, RowVersion và schema payload.",
            "Thiết kế bảng SQL, migration, index và mã hóa credential.",
            "Xây ERPX Internal Storage API và runtime bundle.",
            "Triển khai ERPXStorageAdapter trong package tích hợp riêng.",
            "Triển khai WorkspaceSyncService và manifest/checksum.",
            "Chuyển Agent/Session/Message/State/Credential khỏi RedisStorage.",
            "Chuyển Schedule/Team; kiểm thử concurrency/idempotency/recovery.",
            "Triển khai middleware adapter SQL VECTOR và benchmark.",
            "Quyết định RedisMessageBus hoặc broker thay thế.",
            "Kiểm thử security, load, failover, backup và đa tenant.",
        ],
    )

    doc.add_heading("13. Tiêu chí nghiệm thu", level=1)
    add_bullets(
        doc,
        [
            "ERPX quản lý đầy đủ Agent, Session, Credential, Message, Schedule và Team trong SQL.",
            "AI Service chạy agent mà không truy cập trực tiếp SQL Server.",
            "Message/state không bị ghi trùng khi retry.",
            "Skill/MCP/file đồng bộ đúng version/checksum.",
            "SSE phản ánh đủ trạng thái, lỗi và HITL.",
            "Memory tìm kiếm được bằng cột VECTOR.",
            "Không còn RedisStorage cho record chính; MessageBus được tách riêng.",
            "Không lộ credential qua log, API, workspace hoặc trình duyệt.",
        ],
    )

    doc.add_heading("14. Kết luận", level=1)
    doc.add_paragraph(
        "ERPX Business Service và SQL Server 2025 là nguồn dữ liệu trung tâm; "
        "AI Service Python/ASOFT AI Services tập trung thực thi AI. ERPXStorageAdapter "
        "bảo toàn contract StorageBase để ASOFT AI Services có thể lấy/lưu dữ liệu ở "
        "mọi giai đoạn runtime mà không kết nối SQL trực tiếp. SQL Server lưu "
        "dữ liệu quan hệ/JSON và middleware vector; workspace chỉ giữ bản runtime; "
        "MessageBus tiếp tục là thành phần độc lập cho event và điều phối.",
    )

    for section in doc.sections:
        header = section.header.paragraphs[0]
        header.text = "ERPX - AI Service (Python/ASOFT AI Services) | Kết nối và lưu trữ"
        header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        footer = section.footer.paragraphs[0]
        footer.text = "Tài liệu kiến trúc nội bộ - 30/06/2026"
        footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for paragraph in (header, footer):
            for run in paragraph.runs:
                run.font.name = "Arial"
                run.font.size = Pt(8)
                run.font.color.rgb = RGBColor(100, 100, 100)

    for paragraph in doc.paragraphs:
        if paragraph.style.name.startswith("Heading"):
            paragraph.paragraph_format.keep_with_next = True
        paragraph.paragraph_format.space_after = Pt(5)
        paragraph.paragraph_format.line_spacing = 1.08

    doc.core_properties.title = (
        "Thiết kế kết nối và lưu trữ AI Service ASOFT AI Services cho ERPX"
    )
    doc.core_properties.subject = (
        "ERPX Business Service quản lý SQL Server 2025"
    )
    doc.core_properties.author = "ERPX Engineering"
    doc.core_properties.keywords = (
        "ASOFT AI Services, ERPX, SQL Server 2025, Vector, AI Service, StorageBase"
    )
    return doc


if __name__ == "__main__":
    document = build_document()
    document.save(OUTPUT)
    print(f"Saved: {OUTPUT.resolve()} ({OUTPUT.stat().st_size} bytes)")
