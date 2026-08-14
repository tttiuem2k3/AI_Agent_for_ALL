# Document Conversion Capability

`Capabilities.document_conversion` is the shared document-to-Markdown capability.
It is generic and must not contain ERPX or Knowledge Factory business rules.

## Public structure

```text
document_conversion/
├── __init__.py
├── _base.py
├── _backend.py
├── _errors.py
├── _models.py
├── _service.py
├── _structure.py
├── _native/
└── _vendor/
```

Python consumers only import the public symbols from
`Capabilities.document_conversion`. They must not import `_native` directly.

## Native runtime

`_native/` is a flattened private Rust workspace. There are no nested `src/`
directories inside this capability. Cargo uses explicit `lib.path` entries.

Runtime source synchronized from the maintained fork includes:

- the complete Rust conversion core: formats, model, package, render and shared
- the PyO3 Python binding
- the typed Python native package and stubs
- the upstream dependency lock graph

Node, WASM, benchmark, fuzz, examples, CI and upstream test fixtures are not
runtime dependencies of this Python service and are intentionally not vendored.

The native public artifact is `asoft_document_conversion_native`; application
code reaches it only through `_backend.py` and `DocumentConversionService`.

## Synchronization

Resync from the clean local fork with:

```powershell
.venv\Scripts\python.exe .\src\Capabilities\document_conversion\_vendor\sync_from_fork.py
```

Then verify that parser/render source has no semantic drift:

```powershell
.venv\Scripts\python.exe .\src\Capabilities\document_conversion\_vendor\verify_source_parity.py
```

`_vendor/upstream.json`, `engine_manifest.sha256`, `UPSTREAM_CARGO_LOCK` and the
MIT notice keep the imported engine traceable without exposing upstream branding
through the runtime API.

Build the private wheel on a Rust 1.88+ / Maturin build machine with:

```powershell
.\src\Capabilities\document_conversion\_vendor\build_native.ps1 -Install
```

## Consumers

`Capabilities.rag.DocumentConversionParser` adapts converted Markdown to RAG
`Section` objects while leaving the legacy Word/Excel parser APIs intact.

`ASOFT.knowledge_factory.KnowledgeFactorySourceConverter` is an opt-in business
adapter for source-file conversion. It does not replace the Knowledge Factory
canonical `MarkdownRenderer` for approved ONT2102/ONT2103 data.

Scanned or image-only PDF remains an OCR routing case outside this engine and
is exposed as the stable `DOCUMENT_OCR_REQUIRED` capability error.

## Development environment

`uv sync --all-extras` builds and installs `asoft-document-conversion-native`
from `_native/binding` through `tool.uv.sources`. The validated Windows stack is
Python 3.12.3, uv 0.12.4, Rust 1.97.1 and Maturin 1.14.1.

Native gates: `cargo check --workspace --locked`,
`cargo test --workspace --locked`, and
`cargo clippy --workspace --all-targets --locked -- -D warnings`.

For release packaging, use `scripts/build_release.ps1 -Clean`; the application
and native extension are emitted as separate wheels.
