# Document Conversion Native Runtime

Tài liệu này mô tả cách đồng bộ, build, kiểm thử và phát hành capability
`Capabilities.document_conversion` trong ASOFT AI Services.

## 1. Kiến trúc

Luồng phụ thuộc được cố định theo hướng:

```text
ASOFT business / RAG adapters
        ↓
Capabilities.document_conversion
        ↓
NativeDocumentConversionBackend
        ↓
asoft_document_conversion_native
        ↓
Rust document conversion engine
```

`Capabilities.document_conversion` là capability dùng chung, không chứa rule
ERPX hay Knowledge Factory. `ASOFT.knowledge_factory` chỉ dùng capability thông
qua adapter riêng.

## 2. Cấu trúc mã nguồn

```text
src/Capabilities/document_conversion/
├── __init__.py
├── _base.py
├── _backend.py
├── _errors.py
├── _models.py
├── _service.py
├── _structure.py
├── _native/
│   ├── binding/
│   ├── formats/
│   ├── model/
│   ├── package/
│   ├── render/
│   └── shared/
└── _vendor/
```

`_native` là workspace Rust đã làm phẳng. Không tạo lại các tầng như
`_native_engine/python/src`. `_vendor` chứa tooling đồng bộ, metadata và license.
Runtime `_native` không được chứa nhận diện upstream.

## 3. Nguồn đồng bộ

Nguồn được duy trì tại:

```text
E:\Asoft\anydoc
```

Commit đang ghim và đã kiểm chứng:

```text
e754e1d33a1a540ebc9226e36f11d3f401852c9e
```

Đồng bộ từ fork sạch:

```powershell
.venv\Scripts\python.exe src\Capabilities\document_conversion\_vendor\sync_from_fork.py
.venv\Scripts\python.exe src\Capabilities\document_conversion\_vendor\verify_source_parity.py
```

Verifier hiện kiểm tra source parity, inventory, layout, branding, manifest,
SHA-256 và pinned commit. Kết quả chuẩn hiện tại là `core=66`, `binding=2`,
`python_package=3`, `inventory=76`.

Sau khi làm phẳng workspace, `sync_from_fork.py` dùng `cargo metadata` để
normalize `Cargo.lock` theo dependency graph thực tế. Bước offline được ưu tiên,
chỉ fallback qua registry khi cache local chưa đủ.

## 4. Môi trường build đã kiểm chứng

- Python: 3.12.3 trong `.venv`
- `uv`: 0.12.4
- Rust: 1.97.1 stable
- Maturin: 1.14.1 trong `.venv`
- Visual Studio 2022 Professional với VC++ x64 toolset và Windows SDK

`pyproject.toml` yêu cầu `uv >=0.12.4,<0.13`. Rust tối thiểu của native crate là
1.88. `build_native.ps1` tự tìm `%USERPROFILE%\.cargo\bin` và tự nạp
`vcvars64.bat`, vì vậy không bắt buộc mở Developer PowerShell riêng.

Thiết lập toàn bộ môi trường dev:

```powershell
cd E:\Asoft\ASOFT_AI_SERVICES
uv sync --all-extras
(Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned) ; (& e:\Asoft\ASOFT_AI_SERVICES\.venv\Scripts\Activate.ps1)
```

`uv sync --all-extras` tự build và cài
`asoft-document-conversion-native==0.1.9` từ local source được khai báo trong
`tool.uv.sources`.

## 5. Native validation gates

Từ `_native`:

```powershell
cargo check --workspace --locked
cargo test --workspace --locked
cargo clippy --workspace --all-targets --locked -- -D warnings
```

Trạng thái đã kiểm chứng: `cargo check` PASS, 208 Rust tests PASS, Clippy PASS.
Không auto-format target đã rebrand nếu việc đó làm drift khỏi source fork.

## 6. Build và cài native wheel

Build wheel native và cài lại vào `.venv` hiện tại:

```powershell
.\src\Capabilities\document_conversion\_vendor\build_native.ps1 -Install
```

Artifact Windows hiện tại:

```text
asoft_document_conversion_native-0.1.9-cp310-abi3-win_amd64.whl
```

Wheel dùng ABI3 từ Python 3.10 trở lên. Source Rust, Cargo `target` và tooling
`_vendor` không được đưa vào wheel Python chính.

## 7. Release bundle

Build bundle sạch:

```powershell
.\scripts\build_release.ps1 -Clean
```

`dist/` phải có cả:

```text
asoft_ai_services-<version>-py3-none-any.whl
asoft_document_conversion_native-0.1.9-cp310-abi3-win_amd64.whl
```

Cài bundle vào Python đích:

```powershell
.\scripts\install_release.ps1 -Python C:\path\to\venv\Scripts\python.exe
```

Script cài cả hai wheel và xác minh import native. Quy trình này đã được kiểm
chứng trong một venv tạm sạch và chuyển đổi CSV thật thành Markdown thành công.

## 8. Kiểm thử integration

Fixture native thật nằm tại:

```text
development/tests/fixtures/document_conversion
```

`development/tests/test_document_conversion_native.py` kiểm tra DOC, DOCX,
ODT, RTF, EPUB, PDF, PPT, PPTX, XLS, XLSX, ODS, ODP, CSV, structure, warning PDF
và error document mã hóa.

Các kết quả đã kiểm chứng trong môi trường hiện tại:

- Native fixture + RAG focused tests: 23 PASS
- Full Python regression: 81 PASS
- Native Rust tests: 208 PASS
- Chuyển đổi E2E thủ công trên 13 họ định dạng: PASS

## 9. Quy tắc dependency và packaging

`pyproject.toml` khai báo extra `document-conversion` và `full` bao gồm extra
này. Trong source checkout, `tool.uv.sources` trỏ package native về
`src/Capabilities/document_conversion/_native/binding`.

`requirements.txt` được export từ `uv.lock` và giữ path native ở dạng relative
để dùng trong source checkout. Với release hoặc máy không có source tree, không
cài trực tiếp từ path này; dùng hai wheel trong bundle `dist/`.

`uv.lock` là nguồn khóa dependency chính. Không sửa lockfile bằng tay. Khi thay
`pyproject.toml`, chạy `uv lock` rồi `uv sync --all-extras` và chạy lại toàn bộ
regression tests trước khi commit.
