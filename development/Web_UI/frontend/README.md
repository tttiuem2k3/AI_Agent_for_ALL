# ASOFT AI Services Web UI Test

Frontend React/TypeScript dùng để phát triển và kiểm thử ASOFT AI Service.
Đây là thành phần thuộc `development`, không phải mã nguồn backend production.

## Chức năng

- Cấu hình địa chỉ Python AI Service và `X-User-ID`.
- Quản lý Agent, Credential, Session và Schedule.
- Gửi message và nhận event thời gian thực qua SSE.
- Hiển thị text, thinking, tool call, tool result và yêu cầu xác nhận.
- Quản lý MCP, Skill, Task và Permission của workspace.
- Hỗ trợ giao diện tiếng Việt, tiếng Anh và tiếng Trung.

## Cài đặt và chạy

Chạy từ thư mục workspace Web UI:

```powershell
cd E:\Asoft\ASOFT_AI_SERVICES\development\Web_UI_test
pnpm install
pnpm dev
```

Sau khi mở Web UI, cấu hình Python Server:

```text
http://localhost:8000
```

Nếu truy cập backend từ máy khác trong mạng LAN, sử dụng IP của máy chạy
Python Service, ví dụ:

```text
http://192.168.0.134:8000
```

## Build

```powershell
cd E:\Asoft\ASOFT_AI_SERVICES\development\Web_UI_test
pnpm build
```

## Luồng giao tiếp

```text
Web UI
  → REST API: Agent, Credential, Model, Session, Schedule, Workspace
  → POST /chat/: kích hoạt Chat Run
  ← GET /sessions/{session_id}/stream: nhận AgentEvent qua SSE
```

Business API nằm trong Python package `Service`. Node backend của Web UI hiện
chỉ là lớp hỗ trợ phát triển và health endpoint.
