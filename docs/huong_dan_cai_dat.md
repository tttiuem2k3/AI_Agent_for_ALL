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

### Yêu cầu bổ sung cho document conversion

Nếu cài `--all-extras`, cần thêm Rust stable >=1.88 và Visual Studio 2022 C++
x64 toolset + Windows SDK. `pyproject.toml` hiện yêu cầu `uv >=0.12.4,<0.13`.
Môi trường Windows đã kiểm chứng dùng Python 3.12.3, uv 0.12.4, Rust 1.97.1
và Maturin 1.14.1.


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

### Lưu ý với document conversion native

`uv build --wheel` chỉ tạo wheel Python chính. Khi phát hành bản có document
conversion, phải tạo bundle đầy đủ gồm cả native wheel bằng:

```powershell
.\scripts\build_release.ps1 -Clean
```

Không copy `_native` hoặc `_vendor` vào wheel `asoft-ai-services`.


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

## 12. Document Conversion Native

Từ phiên bản hiện tại, `uv sync --all-extras` còn build và cài native package
`asoft-document-conversion-native==0.1.9`. Máy Windows phát triển capability này
cần thêm:

- `uv >=0.12.4,<0.13`
- Rust stable >=1.88 qua `rustup`
- Visual Studio 2022 với C++ x64 toolset và Windows SDK
- Maturin được cài trong `.venv` thông qua extra `dev`

Môi trường đã kiểm chứng ngày 14/08/2026 dùng Python 3.12.3, `uv 0.12.4`,
Rust 1.97.1 và Maturin 1.14.1.

Cài Rust trên Windows:

```powershell
winget install --id Rustlang.Rustup -e
$env:Path = "$env:USERPROFILE\.cargo\bin;$env:Path"
rustup default stable
rustup component add rustfmt clippy
```

Sau khi `uv sync --all-extras`, có thể kích hoạt đúng `.venv` hiện tại bằng:

```powershell
(Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned) ; (& e:\Asoft\ASOFT_AI_SERVICES\.venv\Scripts\Activate.ps1)
```

Kiểm tra native runtime:

```powershell
python -c "import asoft_document_conversion_native; print(asoft_document_conversion_native.__name__)"
python src\Capabilities\document_conversion\_vendor\verify_source_parity.py
```

Build và cài riêng native wheel:

```powershell
.\src\Capabilities\document_conversion\_vendor\build_native.ps1 -Install
```

Build bundle release gồm cả wheel Python chính và wheel native:

```powershell
.\scripts\build_release.ps1 -Clean
```

Chi tiết xem [Document Conversion Native Runtime](document_conversion_native.md).

### uv báo lockfile version không hỗ trợ

Không sửa `uv.lock` bằng tay. Cài đúng `uv` trong range được khai báo tại
`tool.uv.required-version`, sau đó chạy:

```powershell
uv lock
uv sync --all-extras
```

### Không tìm thấy cargo hoặc rustc

```powershell
$env:Path = "$env:USERPROFILE\.cargo\bin;$env:Path"
rustup default stable
cargo --version
rustc --version
```

### Không tìm thấy MSVC linker

Cài Visual Studio 2022 C++ x64 toolset và Windows SDK. Script
`build_native.ps1` tự tìm Visual Studio qua `vswhere` và nạp `vcvars64.bat`.
