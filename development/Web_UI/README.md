# ASOFT AI Services Web UI

## Chạy môi trường development

Chuẩn bị Python/native ở thư mục gốc dự án:

```powershell
cd E:\Asoft\ASOFT_AI_SERVICES
uv sync --all-extras
```

Chạy ASOFT AI Services API:

```powershell
cd E:\Asoft\ASOFT_AI_SERVICES
.\.venv\Scripts\python.exe service\main.py
```

Mặc định service chạy tại `http://localhost:8000`.
Trong màn hình Setup của Web UI, đặt Server URL thành địa chỉ service này.

Chạy Web UI ở terminal khác:

```powershell
cd E:\Asoft\ASOFT_AI_SERVICES\development\Web_UI
pnpm install
pnpm dev
```

## Test Document Conversion

Mở Web UI và chọn **Document Conversion** ở thanh điều hướng.

Luồng thực tế:

```text
React/Vite Web UI
  -> server_url đã cấu hình, ví dụ http://localhost:8000
  -> GET  /document-conversion/health
  -> POST /document-conversion/convert
  -> service/main.py / Service.app
  -> Capabilities.document_conversion
  -> asoft_document_conversion_native
  -> Markdown
```

Web UI không chạy converter riêng và không gọi Python qua Express bridge.
File được gửi trực tiếp đến ASOFT AI Services dưới dạng binary request body.

Các nhóm hỗ trợ: DOC/DOCX, XLS/XLSX/ODS, PPT/PPTX/ODP, PDF,
CSV/RTF/EPUB/ODT. Giới hạn màn hình test và API là 50 MB.
