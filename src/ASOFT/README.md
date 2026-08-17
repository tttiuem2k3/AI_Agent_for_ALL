# ASOFT custom runtime

`src/ASOFT` contains ASOFT-owned business workflows and ERPX-specific orchestration.
Generic reusable capabilities belong under `src/Capabilities`; provider-specific model
implementations belong under `src/Providers`.

## Current ASOFT workflow

The active knowledge workflow is now:

```text
src/ASOFT/knowledge_factory
```

There is no active `src/ASOFT/knowledge_normalization` package. Do not reintroduce
imports or documentation for that removed module unless a new design explicitly
requires it.

## Knowledge Factory purpose

Knowledge Factory indexes approved ERPX knowledge into canonical Markdown, chunks,
embeddings, and SQL Server vector records.

Current high-level flow:

```text
ERPX publish signal
    -> POST /asoft/knowledge-factory/publish { snapshot_apk }
    -> create/reuse ONT2210 indexing job
    -> worker claims Queued job with lease
    -> load Approved/Published ONT2101 snapshot
    -> load active ONT2102 objects
    -> load Active ONT2103 relations
    -> load ONT2105 source files and convert them to Markdown when present
    -> KnowledgeDocumentBuilder
    -> MarkdownRenderer creates one complete snapshot Markdown file
    -> MarkdownChunker splits that complete Markdown by token size
    -> embedding model embeds each Markdown chunk
    -> write canonical Markdown file
    -> commit CRMT00002 + ONT2220 vectors + ONT2101 activation + ONT2210 success
```

## Current package map

```text
src/ASOFT/
├── README.md
├── __init__.py
└── knowledge_factory/
    ├── _api.py
    ├── _chunking.py
    ├── _config.py
    ├── _document.py
    ├── _document_conversion.py
    ├── _embedding.py
    ├── _errors.py
    ├── _models.py
    ├── _repository.py
    ├── _runtime.py
    ├── _sql.py
    ├── _storage.py
    ├── _vector.py
    └── _worker.py
```

Main responsibilities:

- `_api.py`: server-to-server publish trigger.
- `_repository.py`: SQL Server job/schema/input/commit contract.
- `_worker.py`: polling, lease, canonical document build, chunking, embedding, commit.
- `_document.py`: snapshot metadata + `ONT2102` + `ONT2103` + converted source Markdown -> one complete canonical Markdown file.
- `_chunking.py`: token-window chunks over the complete canonical Markdown file.
- `_embedding.py`: embedding provider composition.
- `_storage.py`: deterministic Markdown file persistence.
- `_vector.py`: SQL Server vector encoding/validation.
- `_document_conversion.py`: opt-in adapter to the generic source document converter.

## Markdown boundary

There are now two different Markdown concepts and they must not be conflated.

### Source document Markdown

Created from original file bytes such as DOCX/PPTX/XLSX/PDF by:

```text
Capabilities.document_conversion
```

Knowledge Factory accesses it only through `KnowledgeFactorySourceConverter` when a
specific source-file use case needs conversion.

### Canonical knowledge Markdown

Created from approved semantic records by:

```text
knowledge_factory._document.MarkdownRenderer
```

This is the Markdown used for indexing and publishing. If source files exist in
`ONT2105`, their converted Markdown is appended as the final section before chunking.

## Generic document conversion dependency

Dependency direction must stay one-way:

```text
ASOFT.knowledge_factory
        -> Capabilities.document_conversion
        -> private native document conversion engine
```

`Capabilities.document_conversion` must never import ERPX/Knowledge Factory business
models, table names, SnapshotAPK, approval status, or indexing-job logic.

## Current DB/runtime invariants

- Only `Approved` or `Published` snapshots are eligible for indexing.
- Active knowledge objects come from `ONT2102` where `IsArchived = 0`.
- Relations used in canonical Markdown come from `ONT2103` where `RelationStatusID = 'Active'`.
- `ONT2210` is the durable Knowledge Factory indexing job/lease table.
- `ONT2220` stores chunks produced from the complete snapshot Markdown and SQL Server vector embeddings.
- Canonical Markdown is registered in `CRMT00002` as an active knowledge document.
- Worker progress/commit is lease-owned; losing the lease must prevent activation.
- Input manifest/hash is recomputed before final activation to prevent stale indexing.
- `ONT2101.NormalizedFileAPK`, content/index fields, and successful job pointer are updated
  only during the final successful indexing transaction.

## Environment

Key settings currently live in `KnowledgeFactorySettings` and use the `ASOFT_AI_KF_*`
namespace. `ASOFT_AI_KF_ENABLED` defaults to true; set it to false only to pause Knowledge Factory processing. SQL configuration is read from the
ERPX KM/SQL connection-string environment variables already supported by `_config.py`.

## Development rule

Before changing Knowledge Factory, read this file and the actual implementation first.
Do not copy generic parsing/conversion code into `src/ASOFT`; add reusable behavior to
`Capabilities` and consume it through a narrow ASOFT adapter.
