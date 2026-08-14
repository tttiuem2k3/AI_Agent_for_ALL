# Repository Guidelines

## Project Structure & Module Organization

Production Python code uses a `src` layout. `src/Runtime` contains agents,
messages, events, and middleware. `src/Providers` contains model, embedding,
OCR, speech, and credential integrations. `src/Capabilities` contains reusable
capabilities such as tools, MCP, permissions, RAG, workspaces, and generic
document conversion. `src/Service` exposes the FastAPI service and storage or
scheduling infrastructure. `src/Common` holds shared utilities.

ASOFT-specific business integration belongs under `src/ASOFT`; do not move
ERPX or Knowledge Factory rules into generic `Capabilities` modules. Keep
runnable examples and integration tests under `development`, and documentation
or diagrams under `docs`.

## Environment & Dependency Management

- Use Python 3.11+ and the `uv` range declared by `tool.uv.required-version`.
- `uv sync --all-extras` is the canonical development environment setup.
- The `document-conversion` extra builds the private PyO3 native package from
  `src/Capabilities/document_conversion/_native/binding` through `tool.uv.sources`.
- Native development on Windows requires Rust stable >=1.88 plus the Visual
  Studio 2022 C++ x64 toolset. The validated toolchain is Rust 1.97.1.
- Maturin belongs in the project `.venv`; do not install project build tooling
  into a shared global Python environment.

## Document Conversion Native Source

`src/Capabilities/document_conversion/_native` is generated from the clean
maintained fork at `E:\Asoft\anydoc`. Do not hand-edit parser or renderer source
there. Resynchronize with `_vendor/sync_from_fork.py`, then run
`_vendor/verify_source_parity.py`.

The flattened target intentionally has no nested `src` directory. `_vendor`
may retain upstream repository names for traceability, but runtime `_native`
must not expose upstream branding. The target binding may format differently
from upstream after ASOFT crate/package renaming, so do not auto-format the
vendored target merely to satisfy rustfmt. Format the maintained fork instead.

Native validation gates are:

```powershell
cargo check --workspace --locked
cargo test --workspace --locked
cargo clippy --workspace --all-targets --locked -- -D warnings
```

## Build, Test, and Release Commands

- `uv sync --all-extras` synchronizes `.venv`, including native conversion.
- `uv run --extra dev pytest` runs the configured development test suite.
- Run `development/tests/test_document_conversion_native.py` for real native
  fixture coverage across document, presentation, spreadsheet, PDF, and CSV families.
- `scripts/build_release.ps1 -Clean` builds the application wheel and the
  native ABI3 wheel into the same `dist/` release bundle.
- `scripts/install_release.ps1 -Python <python.exe>` installs and verifies both
  release wheels in a target Python environment.
- From `development/Web_UI`, run `pnpm install`, then `pnpm dev`; use
  `pnpm build` for production builds and `pnpm format:check` for UI validation.

## Coding Style & Naming Conventions

Use Python 3.11+ syntax, four-space indentation, type hints on public APIs,
`snake_case` for modules/functions, and `PascalCase` for classes. Preserve
stable interfaces between Runtime, Providers, Capabilities, ASOFT, and Service.
TypeScript/TSX follows the existing project formatter and lint configuration.

## Testing Guidelines

Add pytest files as `development/tests/test_*.py`; name tests
`test_<behavior>`. Cover success, validation, async/error paths, and native
integration where applicable. Lazy optional-dependency tests must simulate a
missing import rather than depend on the current `.venv` package set. Run
focused tests during development and the full suite before review.

## Commit & Pull Request Guidelines

Use concise, imperative, scoped subjects. Pull requests should explain behavior
changes, list verification commands, and call out configuration/API impacts.
Never commit API keys, `.env`, `.venv`, `dist`, `build`, generated `*.egg-info`,
or native Cargo `target` directories.

## Agent-Specific Instructions

For code discovery, use the codebase knowledge graph first: `search_graph`,
`trace_path`, then `get_code_snippet`. Use text/file search only for literals,
configuration, non-code files, generated metadata, or when graph results are
insufficient. Never overwrite unrelated working-tree changes while updating a
focused capability.
