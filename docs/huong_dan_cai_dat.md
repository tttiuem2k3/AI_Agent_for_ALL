# Thiết lập ASOFT AI Services

Tài liệu này hướng dẫn thiết lập môi trường phát triển ASOFT AI Services
(Python) cho ERPX trên Windows bằng PowerShell.

## 1. Yêu cầu môi trường

Cần cài đặt:

- Python 3.11 trở lên
- `uv`
- Node.js 20 trở lên
- `pnpm`
- Redis
- Docker Desktop (khuyến nghị để chạy Redis)
- Git

Kiểm tra các phiên bản đã cài:

```powershell
python --version
uv --version
node --version
pnpm --version
docker --version
git --version
```

## 2. Cài đặt công cụ

### Cài uv

```powershell
winget install astral-sh.uv
```

Khởi động lại terminal rồi kiểm tra:

```powershell
uv --version
```

### Kích hoạt pnpm

Node.js đi kèm Corepack, có thể dùng Corepack để cài `pnpm`:

```powershell
corepack enable
corepack prepare pnpm@latest --activate
pnpm --version
```

Nếu Corepack không khả dụng:

```powershell
npm install --global pnpm
```

## 3. Cài Python dependencies

Mở PowerShell tại thư mục dự án:

```powershell
cd E:\Asoft\ASOFT_AI_SERVICES
uv sync --all-extras
```

Lệnh này tạo môi trường `.venv` và cài các dependency từ `pyproject.toml`
và `uv.lock`.

Không cần kích hoạt `.venv` khi sử dụng `uv run`.

## 4. Cấu hình biến môi trường

Ví dụ cấu hình DashScope/Qwen cho terminal hiện tại:

```powershell
$env:DASHSCOPE_API_KEY = "sk-..."
```

Nếu sử dụng Gaode/AMap MCP:

```powershell
$env:AMAP_API_KEY = "..."
```

Các biến được đặt bằng `$env:` chỉ tồn tại trong terminal hiện tại. Không đưa
API key thật vào Git.

## 5. Chạy Redis

### Sử dụng Docker

```powershell
docker run --name asoft-redis -d -p 6379:6379 redis:7
```

Nếu container Redis đã tồn tại nhưng đang dừng:

```powershell
docker start asoft-redis
```

Backend mặc định kết nối Redis tại:

```text
localhost:6379
```

## 6. Chạy backend

Mở một terminal PowerShell mới:

```powershell
cd E:\Asoft\ASOFT_AI_SERVICES
uv run python service\main.py
```

Backend mặc định chạy tại:

```text
http://localhost:8000
```

## 7. Chạy Web UI TEST

Mở một terminal PowerShell khác:

```powershell
cd E:\Asoft\ASOFT_AI_SERVICES\development\Web_UI_test
pnpm install
pnpm dev
```

Mở địa chỉ được Vite hiển thị trên terminal và cấu hình API endpoint:

```text
http://localhost:8000
```

## 8. Chạy kiểm thử

Từ thư mục gốc:

```powershell
cd E:\Asoft\ASOFT_AI_SERVICES
uv run --extra dev pytest development\tests
```

Chỉ kiểm tra quá trình thu thập test:

```powershell
uv run --extra dev pytest --collect-only -q
```

## 9. Build Python package

```powershell
cd E:\Asoft\ASOFT_AI_SERVICES
uv build --wheel
```

Wheel được tạo trong thư mục `dist`. Các thư mục như `.venv`, `dist`, `build`
và `*.egg-info` là artifact cục bộ, không nên commit vào Git.

## 10. Khởi động lại hằng ngày

Terminal 1 — Redis:

```powershell
docker start asoft-redis
```

Terminal 2 — backend:

```powershell
cd E:\Asoft\ASOFT_AI_SERVICES
uv run python service\main.py
```

Terminal 3 — Web UI:

```powershell
cd E:\Asoft\ASOFT_AI_SERVICES\development\Web_UI_test
pnpm dev
```

## 11. Xử lý lỗi thường gặp

### Redis connection refused

Kiểm tra Redis:

```powershell
docker ps
```

Đảm bảo cổng `6379` đã được publish và không bị ứng dụng khác sử dụng.

### Không nhận lệnh uv hoặc pnpm

Đóng rồi mở lại PowerShell sau khi cài đặt. Kiểm tra:

```powershell
Get-Command uv
Get-Command pnpm
```

### Python dependency chưa đồng bộ

```powershell
cd E:\Asoft\ASOFT_AI_SERVICES
uv sync --all-extras
```

### Frontend thiếu dependency

```powershell
cd E:\Asoft\ASOFT_AI_SERVICES\development\Web_UI_test
pnpm install
```
