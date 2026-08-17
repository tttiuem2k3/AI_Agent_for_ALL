# -*- coding: utf-8 -*-
"""SQL Server repository for ONT2210/ONT2220 Knowledge Factory indexing."""
from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from typing import Any

from ._errors import KnowledgeFactoryError, LeaseLostError
from ._models import ActiveRelationRecord, IndexJobRecord, IndexJobStatus, KnowledgeChunk, KnowledgeObjectRecord, NormalizedMarkdownFile, PublishResponse, SnapshotIndexRecord, SourceDocumentRecord
from ._sql import normalize_odbc_connection_string
from ._vector import SQLServerVectorCodec


class KnowledgeFactoryRepository:
    def __init__(self, connection_string: str) -> None:
        if not connection_string.strip():
            raise ValueError("A SQL connection string is required.")
        self._connection_string = normalize_odbc_connection_string(connection_string)

    def _connect(self):
        try:
            import pyodbc
        except ImportError as exc:
            raise RuntimeError("pyodbc is required for Knowledge Factory.") from exc
        return pyodbc.connect(self._connection_string, autocommit=False, timeout=10)

    @staticmethod
    def _rows(cursor) -> list[dict[str, Any]]:
        if cursor.description is None:
            return []
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    async def apply_migrations(self, dimensions: int) -> None:
        await asyncio.to_thread(self._apply_migrations_sync, dimensions)

    def _apply_migrations_sync(self, dimensions: int) -> None:
        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM sys.types WHERE name = 'vector';")
            if int(cursor.fetchone()[0]) != 1:
                raise KnowledgeFactoryError("SQL_VECTOR_NOT_SUPPORTED", "SQL Server vector type is not available.")
            cursor.execute(
                f"""
                IF OBJECT_ID('dbo.ONT2210', 'U') IS NULL
                BEGIN
                    CREATE TABLE dbo.ONT2210 (
                        APK uniqueidentifier NOT NULL CONSTRAINT PK_ONT2210 PRIMARY KEY,
                        DivisionID varchar(50) NOT NULL,
                        SnapshotAPK uniqueidentifier NOT NULL,
                        NormalizedFileAPK uniqueidentifier NULL,
                        ApprovedContentHash char(64) NOT NULL,
                        InputManifestHash char(64) NOT NULL,
                        IndexVersion varchar(30) NOT NULL,
                        JobStatusID varchar(30) NOT NULL,
                        ProgressPercent tinyint NOT NULL CONSTRAINT DF_ONT2210_Progress DEFAULT (0),
                        RetryCount int NOT NULL CONSTRAINT DF_ONT2210_Retry DEFAULT (0),
                        IndexedObjectCount int NOT NULL CONSTRAINT DF_ONT2210_ObjectCount DEFAULT (0),
                        ChunkCount int NOT NULL CONSTRAINT DF_ONT2210_ChunkCount DEFAULT (0),
                        TokenCount int NOT NULL CONSTRAINT DF_ONT2210_TokenCount DEFAULT (0),
                        LastErrorCode varchar(100) NULL,
                        LastErrorMessage nvarchar(max) NULL,
                        CancelledUserID varchar(50) NULL,
                        CancelledDate datetime2 NULL,
                        StartedDate datetime2 NULL,
                        CompletedDate datetime2 NULL,
                        LeaseOwner varchar(100) NULL,
                        LeaseExpiresDate datetime2 NULL,
                        CreateUserID varchar(50) NULL,
                        CreateDate datetime2 NOT NULL CONSTRAINT DF_ONT2210_CreateDate DEFAULT SYSUTCDATETIME(),
                        LastModifyUserID varchar(50) NULL,
                        LastModifyDate datetime2 NULL,
                        RowVersion rowversion NOT NULL
                    );
                    CREATE UNIQUE INDEX UQ_ONT2210_Division_Snapshot ON dbo.ONT2210(DivisionID, SnapshotAPK);
                    CREATE INDEX IX_ONT2210_Queue ON dbo.ONT2210(JobStatusID, LeaseExpiresDate, CreateDate, APK)
                        INCLUDE(DivisionID, SnapshotAPK, RetryCount, ProgressPercent, InputManifestHash);
                END;
                IF OBJECT_ID('dbo.ONT2220', 'U') IS NULL
                BEGIN
                    CREATE TABLE dbo.ONT2220 (
                        ChunkID bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_ONT2220 PRIMARY KEY CLUSTERED,
                        APK uniqueidentifier NOT NULL,
                        DivisionID varchar(50) NOT NULL,
                        JobAPK uniqueidentifier NOT NULL,
                        SnapshotAPK uniqueidentifier NOT NULL,
                        ObjectAPK uniqueidentifier NULL,
                        ChunkSourceType varchar(30) NOT NULL CONSTRAINT DF_ONT2220_ChunkSourceType DEFAULT 'SNAPSHOT_MARKDOWN',
                        SourceFileAPK uniqueidentifier NULL,
                        ChunkIndex int NOT NULL,
                        LookupKey nvarchar(450) NULL,
                        ChunkText nvarchar(max) NOT NULL,
                        TokenCount int NOT NULL,
                        ContentHash char(64) NOT NULL,
                        Embedding vector({dimensions}) NOT NULL,
                        SectionPath nvarchar(max) NULL,
                        SourceLocatorJson nvarchar(max) NULL,
                        CreateDate datetime2 NOT NULL CONSTRAINT DF_ONT2220_CreateDate DEFAULT SYSUTCDATETIME()
                    );
                    CREATE UNIQUE INDEX UQ_ONT2220_APK ON dbo.ONT2220(APK);
                    CREATE UNIQUE INDEX UQ_ONT2220_Job_Object_Chunk ON dbo.ONT2220(JobAPK, ObjectAPK, ChunkIndex);
                    CREATE INDEX IX_ONT2220_Division_Snapshot_Job ON dbo.ONT2220(DivisionID, SnapshotAPK, JobAPK);
                END;
                """,
            )
            cursor.execute("""
                IF OBJECT_ID('dbo.ONT2220', 'U') IS NOT NULL
                BEGIN
                    IF COL_LENGTH('dbo.ONT2220', 'ChunkSourceType') IS NULL
                        ALTER TABLE dbo.ONT2220 ADD ChunkSourceType varchar(30) NOT NULL CONSTRAINT DF_ONT2220_ChunkSourceType DEFAULT 'SNAPSHOT_MARKDOWN';
                    IF COL_LENGTH('dbo.ONT2220', 'SourceFileAPK') IS NULL
                        ALTER TABLE dbo.ONT2220 ADD SourceFileAPK uniqueidentifier NULL;
                    IF EXISTS (
                        SELECT 1 FROM sys.columns
                        WHERE object_id = OBJECT_ID('dbo.ONT2220')
                          AND name = 'ObjectAPK'
                          AND is_nullable = 0
                    )
                        ALTER TABLE dbo.ONT2220 ALTER COLUMN ObjectAPK uniqueidentifier NULL;
                END;
            """)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    async def validate_schema_contract(self, dimensions: int) -> None:
        await asyncio.to_thread(self._validate_schema_contract_sync, dimensions)

    def _validate_schema_contract_sync(self, dimensions: int) -> None:
        required = {
            "ONT2210": {"APK", "DivisionID", "SnapshotAPK", "NormalizedFileAPK", "ApprovedContentHash", "InputManifestHash", "IndexVersion", "JobStatusID", "ProgressPercent", "RetryCount", "IndexedObjectCount", "ChunkCount", "TokenCount", "LeaseOwner", "LeaseExpiresDate"},
            "ONT2220": {"ChunkID", "APK", "DivisionID", "JobAPK", "SnapshotAPK", "ObjectAPK", "ChunkSourceType", "SourceFileAPK", "ChunkIndex", "ChunkText", "TokenCount", "ContentHash", "Embedding", "SectionPath", "SourceLocatorJson"},
        }
        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute("""
                SELECT t.name AS TableName, c.name AS ColumnName
                FROM sys.tables t JOIN sys.columns c ON c.object_id = t.object_id
                WHERE t.name IN ('ONT2210', 'ONT2220');
            """)
            present: dict[str, set[str]] = {}
            for row in self._rows(cursor):
                present.setdefault(str(row["TableName"]), set()).add(str(row["ColumnName"]))
            missing = [f"{table}.{column}" for table, columns in required.items() for column in sorted(columns - present.get(table, set()))]
            if missing:
                raise KnowledgeFactoryError("DB_SCHEMA_NOT_READY", "Knowledge Factory DB schema is missing: " + ", ".join(missing))
            cursor.execute(
                """
                SELECT vector_dimensions
                FROM sys.columns
                WHERE object_id = OBJECT_ID('dbo.ONT2220')
                  AND name = 'Embedding';
                """,
            )
            row = cursor.fetchone()
            actual_schema_dimensions = int(row[0]) if row and row[0] else 0
            if actual_schema_dimensions != dimensions:
                raise KnowledgeFactoryError(
                    "VECTOR_DIMENSION_MISMATCH",
                    f"ONT2220.Embedding expects {actual_schema_dimensions} dimensions, configured {dimensions}.",
                )
            cursor.execute(
                "SELECT CAST(VECTORPROPERTY(CAST(CAST(? AS varchar(max)) AS vector(%d)), 'Dimensions') AS int);" % dimensions,
                "[" + ",".join("0" for _ in range(dimensions)) + "]",
            )
            actual_dimensions = int(cursor.fetchone()[0])
            if actual_dimensions != dimensions:
                raise KnowledgeFactoryError(
                    "VECTOR_DIMENSION_MISMATCH",
                    f"SQL vector dimension mismatch: expected {dimensions}, got {actual_dimensions}.",
                )
            connection.rollback()
        finally:
            connection.close()

    async def enqueue_publish(self, snapshot_apk: str, index_version: str) -> PublishResponse:
        return await asyncio.to_thread(self._enqueue_publish_sync, snapshot_apk, index_version)

    def _enqueue_publish_sync(self, snapshot_apk: str, index_version: str) -> PublishResponse:
        connection = self._connect()
        try:
            cursor = connection.cursor()
            snapshot = self._get_snapshot(cursor, snapshot_apk)
            self._validate_snapshot_ready(snapshot)
            manifest_hash = self._compute_input_manifest_hash(cursor, snapshot)
            approved_hash = snapshot.approved_content_hash or manifest_hash
            cursor.execute("""
                SELECT TOP (1) APK, JobStatusID, InputManifestHash, IndexVersion
                FROM dbo.ONT2210 WITH (UPDLOCK, HOLDLOCK)
                WHERE DivisionID = ? AND SnapshotAPK = ?;
            """, snapshot.division_id, snapshot.apk)
            rows = self._rows(cursor)
            if rows:
                job_apk = str(rows[0]["APK"])
                status = IndexJobStatus(str(rows[0]["JobStatusID"]))
                input_changed = str(rows[0]["InputManifestHash"]) != manifest_hash
                version_changed = str(rows[0]["IndexVersion"]) != index_version
                retryable = status in {IndexJobStatus.FAILED, IndexJobStatus.CANCELLED}
                if status != IndexJobStatus.PROCESSING and (input_changed or version_changed or retryable):
                    cursor.execute("""
                        UPDATE dbo.ONT2210 SET
                            ApprovedContentHash = ?, InputManifestHash = ?, IndexVersion = ?,
                            JobStatusID = 'Queued', ProgressPercent = 0, RetryCount = 0,
                            IndexedObjectCount = 0, ChunkCount = 0, TokenCount = 0,
                            LastErrorCode = NULL, LastErrorMessage = NULL,
                            StartedDate = NULL, CompletedDate = NULL,
                            LeaseOwner = NULL, LeaseExpiresDate = NULL,
                            LastModifyUserID = 'KM_FACTORY', LastModifyDate = SYSUTCDATETIME()
                        WHERE APK = ? AND DivisionID = ? AND SnapshotAPK = ?;
                    """, approved_hash, manifest_hash, index_version, job_apk, snapshot.division_id, snapshot.apk)
                    status = IndexJobStatus.QUEUED
            else:
                job_apk = str(uuid.uuid4()).upper()
                cursor.execute("""
                    INSERT INTO dbo.ONT2210
                    (APK, DivisionID, SnapshotAPK, NormalizedFileAPK, ApprovedContentHash,
                     InputManifestHash, IndexVersion, JobStatusID, CreateUserID, CreateDate)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'Queued', 'KM_FACTORY', SYSUTCDATETIME());
                """, job_apk, snapshot.division_id, snapshot.apk, snapshot.normalized_file_apk, approved_hash, manifest_hash, index_version)
                status = IndexJobStatus.QUEUED
            connection.commit()
            details = {
                IndexJobStatus.QUEUED: "Knowledge Factory indexing job is queued.",
                IndexJobStatus.PROCESSING: "Knowledge Factory indexing job is processing.",
                IndexJobStatus.SUCCEEDED: "Knowledge Factory indexing job already succeeded.",
                IndexJobStatus.FAILED: "Knowledge Factory indexing job failed.",
                IndexJobStatus.CANCELLED: "Knowledge Factory indexing job was cancelled.",
            }
            return PublishResponse(snapshot_apk=snapshot.apk, job_apk=job_apk, status=status, detail=details[status])
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    async def claim_next(self, worker_id: str, lease_seconds: int, max_reclaims: int) -> IndexJobRecord | None:
        return await asyncio.to_thread(self._claim_next_sync, worker_id, lease_seconds, max_reclaims)

    def _claim_next_sync(self, worker_id: str, lease_seconds: int, max_reclaims: int) -> IndexJobRecord | None:
        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute("""
                ;WITH next_job AS (
                    SELECT TOP (1) * FROM dbo.ONT2210 WITH (UPDLOCK, READPAST, ROWLOCK)
                    WHERE JobStatusID = 'Queued'
                       OR (JobStatusID = 'Processing' AND LeaseExpiresDate < SYSUTCDATETIME() AND RetryCount < ?)
                    ORDER BY CreateDate, APK
                )
                UPDATE next_job
                   SET JobStatusID = 'Processing', ProgressPercent = CASE WHEN ProgressPercent < 5 THEN 5 ELSE ProgressPercent END,
                       RetryCount = CASE WHEN JobStatusID = 'Processing' THEN RetryCount + 1 ELSE RetryCount END,
                       LeaseOwner = ?, LeaseExpiresDate = DATEADD(second, ?, SYSUTCDATETIME()),
                       StartedDate = COALESCE(StartedDate, SYSUTCDATETIME()), LastModifyUserID = 'KM_FACTORY', LastModifyDate = SYSUTCDATETIME()
                OUTPUT inserted.APK, inserted.DivisionID, inserted.SnapshotAPK, inserted.JobStatusID, inserted.IndexVersion,
                       inserted.ApprovedContentHash, inserted.InputManifestHash, inserted.RetryCount, inserted.ProgressPercent,
                       inserted.LeaseOwner, inserted.LeaseExpiresDate;
            """, max_reclaims, worker_id, lease_seconds)
            rows = self._rows(cursor)
            connection.commit()
            return self._job(rows[0]) if rows else None
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    async def load_index_input(self, job: IndexJobRecord) -> tuple[SnapshotIndexRecord, list[KnowledgeObjectRecord], list[ActiveRelationRecord]]:
        return await asyncio.to_thread(self._load_index_input_sync, job)

    async def load_source_documents(self, job: IndexJobRecord) -> list[SourceDocumentRecord]:
        return await asyncio.to_thread(self._load_source_documents_sync, job)

    def _load_source_documents_sync(self, job: IndexJobRecord) -> list[SourceDocumentRecord]:
        connection = self._connect()
        try:
            return self._load_source_documents(connection.cursor(), job)
        finally:
            connection.close()

    def _load_source_documents(self, cursor, job: IndexJobRecord) -> list[SourceDocumentRecord]:
        cursor.execute("""
            SELECT FileAPK, SourceOrdinal, SourceFileName, MimeType, SourceContentHash
            FROM dbo.ONT2105
            WHERE SnapshotAPK = ?
            ORDER BY SourceOrdinal, FileAPK;
        """, job.snapshot_apk)
        return [
            SourceDocumentRecord(
                file_apk=str(row["FileAPK"]),
                source_ordinal=int(row["SourceOrdinal"]),
                source_file_name=str(row["SourceFileName"]),
                mime_type=str(row["MimeType"]) if row["MimeType"] else None,
                source_content_hash=str(row["SourceContentHash"]) if row["SourceContentHash"] else None,
            )
            for row in self._rows(cursor)
        ]

    def _load_index_input_sync(self, job: IndexJobRecord):
        connection = self._connect()
        try:
            cursor = connection.cursor()
            snapshot = self._get_snapshot(cursor, job.snapshot_apk)
            objects = self._load_objects(cursor, job)
            relations = self._load_relations(cursor, job)
            connection.rollback()
            return snapshot, objects, relations
        finally:
            connection.close()

    async def get_web_physical_path(self) -> str:
        return await asyncio.to_thread(self._get_web_physical_path_sync)

    def _get_web_physical_path_sync(self) -> str:
        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT TOP (2) KeyValue FROM dbo.ST2101
                WHERE GroupID = 1 AND KeyName = 'WebPhysicalPath';
                """,
            )
            rows = self._rows(cursor)
            connection.rollback()
        finally:
            connection.close()
        values = [str(row["KeyValue"]).strip() for row in rows if row.get("KeyValue")]
        if len(values) != 1:
            raise KnowledgeFactoryError(
                "WEB_PHYSICAL_PATH_INVALID",
                "ST2101 must contain exactly one WebPhysicalPath setting.",
            )
        return values[0]

    async def heartbeat(self, job: IndexJobRecord, worker_id: str, lease_seconds: int, progress: int) -> None:
        await asyncio.to_thread(self._heartbeat_sync, job, worker_id, lease_seconds, progress)

    def _heartbeat_sync(self, job: IndexJobRecord, worker_id: str, lease_seconds: int, progress: int) -> None:
        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute("""
                UPDATE dbo.ONT2210 SET ProgressPercent = ?, LeaseExpiresDate = DATEADD(second, ?, SYSUTCDATETIME()), LastModifyDate = SYSUTCDATETIME()
                WHERE APK = ? AND DivisionID = ? AND SnapshotAPK = ? AND JobStatusID = 'Processing' AND LeaseOwner = ? AND LeaseExpiresDate > SYSUTCDATETIME();
            """, progress, lease_seconds, job.apk, job.division_id, job.snapshot_apk, worker_id)
            if cursor.rowcount != 1:
                raise LeaseLostError()
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    async def commit_success(
        self,
        job: IndexJobRecord,
        worker_id: str,
        markdown_file: NormalizedMarkdownFile,
        chunks: list[KnowledgeChunk],
        embeddings: list[list[float]],
        dimensions: int,
    ) -> None:
        await asyncio.to_thread(
            self._commit_success_sync,
            job,
            worker_id,
            markdown_file,
            chunks,
            embeddings,
            dimensions,
        )

    def _commit_success_sync(
        self,
        job: IndexJobRecord,
        worker_id: str,
        markdown_file: NormalizedMarkdownFile,
        chunks: list[KnowledgeChunk],
        embeddings: list[list[float]],
        dimensions: int,
    ) -> None:
        if len(chunks) != len(embeddings):
            raise KnowledgeFactoryError(
                "EMBEDDING_COUNT_MISMATCH",
                "Embedding output count differs from chunk count.",
            )
        connection = self._connect()
        try:
            cursor = connection.cursor()
            snapshot = self._get_snapshot(cursor, job.snapshot_apk)
            current_manifest_hash = self._compute_input_manifest_hash(cursor, snapshot)
            if current_manifest_hash != job.input_manifest_hash:
                raise KnowledgeFactoryError("INDEX_INPUT_CHANGED", "Approved knowledge changed while indexing.")
            cursor.execute(
                """
                INSERT INTO dbo.CRMT00002
                (APK, DivisionID, AttachName, CreateDate, CreateUserID,
                 FileSize, MimeType, ContentHash, FileStatus, FileCategoryID)
                VALUES (?, ?, ?, SYSUTCDATETIME(), 'KM_FACTORY', ?,
                        'text/markdown', ?, 'ACTIVE', 'KNOWLEDGE_DOCUMENT');
                """,
                markdown_file.apk,
                job.division_id,
                markdown_file.attach_name,
                markdown_file.file_size,
                markdown_file.content_hash,
            )
            cursor.execute("DELETE FROM dbo.ONT2220 WHERE JobAPK = ?;", job.apk)
            for chunk, vector in zip(chunks, embeddings):
                cursor.execute(
                    f"""
                    INSERT INTO dbo.ONT2220
                    (APK, DivisionID, JobAPK, SnapshotAPK, ObjectAPK, ChunkSourceType, SourceFileAPK, ChunkIndex,
                     LookupKey, ChunkText, TokenCount, ContentHash, Embedding,
                     SectionPath, SourceLocatorJson, CreateDate)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            CAST(CAST(? AS varchar(max)) AS vector({dimensions})), ?, ?, SYSUTCDATETIME());
                    """,
                    str(uuid.uuid4()).upper(),
                    job.division_id,
                    job.apk,
                    job.snapshot_apk,
                    chunk.object_apk,
                    chunk.source_locator_json.get("source_type", "SNAPSHOT_MARKDOWN"),
                    chunk.source_locator_json.get("source_file_apk"),
                    chunk.chunk_index,
                    f"{job.snapshot_apk}:{chunk.source_locator_json.get('source_type', 'SNAPSHOT_MARKDOWN')}:{chunk.chunk_index}",
                    chunk.chunk_text,
                    chunk.token_count,
                    chunk.content_hash,
                    SQLServerVectorCodec.to_sql_literal(vector, dimensions=dimensions),
                    chunk.section_path,
                    json.dumps(
                        chunk.source_locator_json,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                )
            object_count = len(self._load_objects(cursor, job))
            token_count = sum(chunk.token_count for chunk in chunks)
            cursor.execute(
                """
                UPDATE dbo.ONT2210 SET JobStatusID = 'Succeeded',
                    ProgressPercent = 100, IndexedObjectCount = ?, ChunkCount = ?,
                    TokenCount = ?, NormalizedFileAPK = ?, CompletedDate = SYSUTCDATETIME(),
                    LeaseOwner = NULL, LeaseExpiresDate = NULL,
                    LastErrorCode = NULL, LastErrorMessage = NULL,
                    LastModifyUserID = 'KM_FACTORY', LastModifyDate = SYSUTCDATETIME()
                WHERE APK = ? AND DivisionID = ? AND SnapshotAPK = ?
                  AND JobStatusID = 'Processing' AND LeaseOwner = ?
                  AND LeaseExpiresDate > SYSUTCDATETIME();
                """,
                object_count,
                len(chunks),
                token_count,
                markdown_file.apk,
                job.apk,
                job.division_id,
                job.snapshot_apk,
                worker_id,
            )
            if cursor.rowcount != 1:
                raise LeaseLostError()
            cursor.execute(
                """
                UPDATE dbo.ONT2101 SET
                    NormalizedFileAPK = ?,
                    ContentHash = ?,
                    ApprovedContentHash = COALESCE(ApprovedContentHash, ?),
                    SuccessfulJobAPK = ?, IndexVersion = ?,
                    LastModifyUserID = 'KM_FACTORY', LastModifyDate = SYSUTCDATETIME()
                WHERE APK = ? AND DivisionID = ?
                  AND (ApprovedContentHash = ? OR ApprovedContentHash IS NULL);
                """,
                markdown_file.apk,
                markdown_file.content_hash,
                markdown_file.content_hash,
                job.apk,
                job.index_version,
                job.snapshot_apk,
                job.division_id,
                job.approved_content_hash,
            )
            if cursor.rowcount != 1:
                raise KnowledgeFactoryError(
                    "SNAPSHOT_ACTIVATION_CONFLICT",
                    "The approved snapshot changed before index activation.",
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    async def fail_job(self, job: IndexJobRecord, worker_id: str, code: str, message: str) -> None:
        await asyncio.to_thread(self._fail_job_sync, job, worker_id, code[:100], message[:4000])

    def _fail_job_sync(self, job: IndexJobRecord, worker_id: str, code: str, message: str) -> None:
        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute("""
                UPDATE dbo.ONT2210 SET JobStatusID = 'Failed', ProgressPercent = 100, CompletedDate = SYSUTCDATETIME(),
                    LeaseOwner = NULL, LeaseExpiresDate = NULL, LastErrorCode = ?, LastErrorMessage = ?, LastModifyUserID = 'KM_FACTORY', LastModifyDate = SYSUTCDATETIME()
                WHERE APK = ? AND DivisionID = ? AND SnapshotAPK = ? AND JobStatusID = 'Processing' AND LeaseOwner = ?;
            """, code, message, job.apk, job.division_id, job.snapshot_apk, worker_id)
            connection.commit()
        finally:
            connection.close()

    def _get_snapshot(self, cursor, snapshot_apk: str) -> SnapshotIndexRecord:
        cursor.execute("""
            SELECT TOP (2) s.APK, s.DivisionID, s.APKMaster AS AssetAPK, a.AssetID, a.Title AS AssetTitle,
                   a.Summary AS AssetSummary, a.PrimaryDomainAPK, a.TypeAPK, a.DepartmentID, a.ModuleID, a.ScreenID,
                   s.VersionNo AS SnapshotVersionNo, s.SnapshotStatusID, s.NormalizedFileAPK, s.ContentHash,
                   s.ApprovedContentHash, s.SuccessfulJobAPK, s.IndexVersion
            FROM dbo.ONT2101 s INNER JOIN dbo.ONT2100 a ON a.APK = s.APKMaster AND a.DivisionID = s.DivisionID
            WHERE s.APK = ?;
        """, snapshot_apk)
        rows = self._rows(cursor)
        if len(rows) != 1:
            raise KnowledgeFactoryError("SNAPSHOT_NOT_FOUND", "Snapshot was not found.")
        row = rows[0]
        tags = self._load_asset_tags(cursor, str(row["AssetAPK"]))
        return SnapshotIndexRecord(
            apk=str(row["APK"]), division_id=str(row["DivisionID"]), asset_apk=str(row["AssetAPK"]),
            asset_id=str(row["AssetID"]) if row["AssetID"] else None, asset_title=str(row["AssetTitle"]),
            asset_summary=str(row["AssetSummary"]) if row["AssetSummary"] else None,
            primary_domain_apk=str(row["PrimaryDomainAPK"]) if row["PrimaryDomainAPK"] else None,
            type_apk=str(row["TypeAPK"]) if row["TypeAPK"] else None, department_id=str(row["DepartmentID"]) if row["DepartmentID"] else None,
            module_id=str(row["ModuleID"]) if row["ModuleID"] else None, screen_id=str(row["ScreenID"]) if row["ScreenID"] else None,
            tag_apks=tags, snapshot_version_no=int(row["SnapshotVersionNo"]), snapshot_status_id=str(row["SnapshotStatusID"]),
            normalized_file_apk=str(row["NormalizedFileAPK"]) if row["NormalizedFileAPK"] else None,
            content_hash=str(row["ContentHash"]) if row["ContentHash"] else None, approved_content_hash=str(row["ApprovedContentHash"]) if row["ApprovedContentHash"] else None,
            successful_job_apk=str(row["SuccessfulJobAPK"]) if row["SuccessfulJobAPK"] else None, index_version=str(row["IndexVersion"]) if row["IndexVersion"] else None,
        )

    def _load_asset_tags(self, cursor, asset_apk: str) -> list[str]:
        cursor.execute("""
            SELECT TagAPK
            FROM dbo.ONT2104
            WHERE APKMaster = ?
            ORDER BY CreateDate, TagAPK;
        """, asset_apk)
        return [str(row["TagAPK"]) for row in self._rows(cursor)]

    def _validate_snapshot_ready(self, snapshot: SnapshotIndexRecord) -> None:
        if snapshot.snapshot_status_id not in {"Approved", "Published"}:
            raise KnowledgeFactoryError("SNAPSHOT_STATUS_INELIGIBLE", "Only Approved or Published snapshots can be indexed.")
        if not snapshot.asset_title.strip():
            raise KnowledgeFactoryError("SNAPSHOT_TITLE_EMPTY", "Knowledge asset title is empty.")

    def _compute_input_manifest_hash(self, cursor, snapshot: SnapshotIndexRecord) -> str:
        objects = self._load_objects(cursor, IndexJobRecord(apk=str(uuid.uuid4()), division_id=snapshot.division_id, snapshot_apk=snapshot.apk, status=IndexJobStatus.QUEUED, index_version="", approved_content_hash=snapshot.approved_content_hash or "", input_manifest_hash=""))
        manifest_job = IndexJobRecord(apk=str(uuid.uuid4()), division_id=snapshot.division_id, snapshot_apk=snapshot.apk, status=IndexJobStatus.QUEUED, index_version="", approved_content_hash=snapshot.approved_content_hash or "", input_manifest_hash="")
        relations = self._load_relations(cursor, manifest_job)
        sources = self._load_source_documents(cursor, manifest_job)
        payload = {
            "snapshot": snapshot.model_dump(),
            "objects": [item.model_dump() for item in objects],
            "relations": [item.model_dump() for item in relations],
            "source_documents": [item.model_dump() for item in sources],
        }
        return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest().upper()

    def _load_objects(self, cursor, job: IndexJobRecord) -> list[KnowledgeObjectRecord]:
        cursor.execute("""
            SELECT APK, ObjectKey, Title, Summary, Content, ParentAPK, DisplayOrder, ModuleID, ScreenID, MetadataJson, SourceLocatorJson
            FROM dbo.ONT2102
            WHERE DivisionID = ? AND SnapshotAPK = ? AND IsArchived = 0
            ORDER BY ISNULL(ParentAPK, '00000000-0000-0000-0000-000000000000'), DisplayOrder, ObjectKey;
        """, job.division_id, job.snapshot_apk)
        rows = self._rows(cursor)
        if not rows:
            raise KnowledgeFactoryError("OBJECTS_EMPTY", "Snapshot has no active knowledge objects to index.")
        return [KnowledgeObjectRecord(apk=str(row["APK"]), object_key=str(row["ObjectKey"]), title=str(row["Title"]), summary=str(row["Summary"]) if row["Summary"] else None, content=str(row["Content"]), parent_apk=str(row["ParentAPK"]) if row["ParentAPK"] else None, display_order=int(row["DisplayOrder"]), module_id=str(row["ModuleID"]) if row["ModuleID"] else None, screen_id=str(row["ScreenID"]) if row["ScreenID"] else None, metadata_json=self._json(row["MetadataJson"]), source_locator_json=self._json(row["SourceLocatorJson"])) for row in rows]

    def _load_relations(self, cursor, job: IndexJobRecord) -> list[ActiveRelationRecord]:
        cursor.execute("""
            SELECT r.APK, r.SourceObjectAPK, r.TargetObjectAPK, r.TargetAssetAPK, a.Title AS TargetAssetTitle,
                   r.TargetObjectKey, r.RelationTypeID, r.Description, r.ConditionText
            FROM dbo.ONT2103 r
            LEFT JOIN dbo.ONT2100 a ON a.APK = r.TargetAssetAPK AND a.DivisionID = r.DivisionID
            WHERE r.DivisionID = ? AND r.SnapshotAPK = ? AND r.RelationStatusID = 'Active'
            ORDER BY r.RelationTypeID, r.APK;
        """, job.division_id, job.snapshot_apk)
        return [ActiveRelationRecord(apk=str(row["APK"]), source_object_apk=str(row["SourceObjectAPK"]), target_object_apk=str(row["TargetObjectAPK"]) if row["TargetObjectAPK"] else None, target_asset_apk=str(row["TargetAssetAPK"]) if row["TargetAssetAPK"] else None, target_asset_title=str(row["TargetAssetTitle"]) if row.get("TargetAssetTitle") else None, target_object_key=str(row["TargetObjectKey"]) if row["TargetObjectKey"] else None, relation_type_id=str(row["RelationTypeID"]), description=str(row["Description"]) if row["Description"] else None, condition_text=str(row["ConditionText"]) if row["ConditionText"] else None) for row in self._rows(cursor)]

    @staticmethod
    def _json(value: Any) -> dict[str, Any]:
        if not value:
            return {}
        if isinstance(value, dict):
            return value
        try:
            parsed = json.loads(str(value))
        except json.JSONDecodeError:
            return {"raw": str(value)}
        return parsed if isinstance(parsed, dict) else {"value": parsed}

    @staticmethod
    def _job(row: dict[str, Any]) -> IndexJobRecord:
        return IndexJobRecord(apk=str(row["APK"]), division_id=str(row["DivisionID"]), snapshot_apk=str(row["SnapshotAPK"]), status=IndexJobStatus(str(row["JobStatusID"])), index_version=str(row["IndexVersion"]), approved_content_hash=str(row["ApprovedContentHash"]), input_manifest_hash=str(row["InputManifestHash"]), retry_count=int(row["RetryCount"]), progress_percent=int(row["ProgressPercent"]), lease_owner=str(row["LeaseOwner"]) if row["LeaseOwner"] else None, lease_expires_date=row["LeaseExpiresDate"])





