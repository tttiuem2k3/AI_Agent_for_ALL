# -*- coding: utf-8 -*-
"""Generate the ERPX P0 assignable-tool manifest and SQL artifacts.

The Python runtime is the source of truth for FunctionName,
DescriptionForLLM, and InputSchemaJson. ERPX policy owns only stable ToolID,
localized catalog text, grouping, read/write classification, and approval.

Production database deployment consumes the committed SQL artifacts; it never
imports or executes this Python module.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys
import tempfile
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from _version import __version__  # noqa: E402
from Capabilities.tool import RegisteredTool  # noqa: E402
from Capabilities.workspace import LocalWorkspace  # noqa: E402


CORES_ROOT = REPOSITORY_ROOT.parent
MANIFEST_PATH = (
    CORES_ROOT
    / "01.ERPX"
    / "_ARCHITECTURE"
    / "_DOCS_ON"
    / "contracts"
    / "tool-catalog-manifest-v1.example.json"
)
SEED_PATH = (
    CORES_ROOT
    / "04.FIXS"
    / "04.ERPX"
    / "7.DATA_MASTER_ERPX"
    / "03_ONT1020-ONT1021_Data.sql"
)

EXPECTED_FUNCTION_NAMES = frozenset(
    {"Bash", "Read", "Write", "Edit", "Glob", "Grep"},
)
FORBIDDEN_TEXT_PATTERNS = (
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"\b(?:password|client_secret|access_token)\s*[:=]", re.IGNORECASE),
    re.compile(r"\b(?:server|data source)\s*=", re.IGNORECASE),
)


@dataclass(frozen=True)
class ToolPolicy:
    """Source-controlled ERPX metadata that cannot be derived from Python."""

    tool_id: str
    function_name: str
    tool_name: str
    description: str
    tool_group: str
    is_read_only: bool
    require_approval: bool


TOOL_POLICIES = (
    ToolPolicy(
        "ASCOPE_BASH",
        "Bash",
        "Chạy lệnh terminal",
        "Chạy lệnh shell trong vùng làm việc được cấp quyền.",
        "Code",
        False,
        True,
    ),
    ToolPolicy(
        "ASCOPE_READ",
        "Read",
        "Đọc tệp",
        "Đọc nội dung tệp được cấp quyền trong vùng làm việc.",
        "DocumentsFiles",
        True,
        True,
    ),
    ToolPolicy(
        "ASCOPE_WRITE",
        "Write",
        "Ghi tệp",
        "Tạo mới hoặc ghi đè tệp được cấp quyền trong vùng làm việc.",
        "DocumentsFiles",
        False,
        True,
    ),
    ToolPolicy(
        "ASCOPE_EDIT",
        "Edit",
        "Sửa tệp",
        "Thay thế chính xác nội dung trong tệp được cấp quyền.",
        "DocumentsFiles",
        False,
        True,
    ),
    ToolPolicy(
        "ASCOPE_GLOB",
        "Glob",
        "Tìm tệp",
        "Tìm các tệp được cấp quyền theo mẫu đường dẫn.",
        "DocumentsFiles",
        True,
        True,
    ),
    ToolPolicy(
        "ASCOPE_GREP",
        "Grep",
        "Tìm trong tệp",
        "Tìm nội dung trong các tệp được cấp quyền theo từ khóa hoặc biểu thức.",
        "DocumentsFiles",
        True,
        True,
    ),
)


def _canonical_json(value: Any, *, pretty: bool) -> str:
    if pretty:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        ) + "\n"
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _validate_no_runtime_leak(value: Any, temporary_root: Path) -> None:
    serialized = _canonical_json(value, pretty=False)
    normalized_temp = str(temporary_root.resolve()).replace("\\", "/")
    if normalized_temp.lower() in serialized.replace("\\", "/").lower():
        raise ValueError("Generated manifest contains the temporary workspace path.")
    for pattern in FORBIDDEN_TEXT_PATTERNS:
        if pattern.search(serialized):
            raise ValueError(
                f"Generated manifest contains forbidden runtime/config text: "
                f"{pattern.pattern}",
            )


async def build_manifest() -> dict[str, Any]:
    """Instantiate the real LocalWorkspace tools and build the P0 manifest."""

    with tempfile.TemporaryDirectory(prefix="erpx-tool-manifest-") as directory:
        temporary_root = Path(directory)
        workspace = LocalWorkspace(workdir=str(temporary_root))
        runtime_tools = {
            tool.name: tool
            for tool in await workspace.list_tools()
        }
        if set(runtime_tools) != EXPECTED_FUNCTION_NAMES:
            raise ValueError(
                "LocalWorkspace assignable tool drift: expected "
                f"{sorted(EXPECTED_FUNCTION_NAMES)}, got {sorted(runtime_tools)}.",
            )

        policies = {policy.function_name: policy for policy in TOOL_POLICIES}
        if set(policies) != EXPECTED_FUNCTION_NAMES:
            raise ValueError("ERPX ToolPolicy mapping does not cover exactly six tools.")

        entries: list[dict[str, Any]] = []
        for policy in sorted(TOOL_POLICIES, key=lambda item: item.tool_id):
            tool = runtime_tools[policy.function_name]
            if bool(tool.is_read_only) != policy.is_read_only:
                raise ValueError(
                    f"IsReadOnly drift for {policy.function_name}: runtime="
                    f"{tool.is_read_only}, ERPX={policy.is_read_only}.",
                )
            function_schema = RegisteredTool(tool).get_tool_schema()["function"]
            if function_schema["name"] != policy.function_name:
                raise ValueError(
                    f"FunctionName drift for {policy.tool_id}: "
                    f"{function_schema['name']}.",
                )
            entries.append(
                {
                    "description": policy.description,
                    "descriptionForLLM": function_schema["description"],
                    "disabled": False,
                    "divisionId": "@@@",
                    "functionName": function_schema["name"],
                    "inputSchema": function_schema["parameters"],
                    "isCommon": True,
                    "isReadOnly": policy.is_read_only,
                    "isSystem": True,
                    "outputSchema": None,
                    "requireApproval": policy.require_approval,
                    "toolGroup": policy.tool_group,
                    "toolId": policy.tool_id,
                    "toolName": policy.tool_name,
                    "toolType": "Builtin",
                },
            )

        manifest = {
            "$schema": "./tool-catalog-manifest-v1.schema.json",
            "catalogId": "erpx.on.assignable-tools",
            "manifestVersion": "1.0",
            "sourceRuntime": {
                "name": "asoft-ai-services",
                "schemaSource": (
                    "LocalWorkspace.list_tools() + "
                    "RegisteredTool.get_tool_schema()"
                ),
                "version": __version__,
            },
            "tools": entries,
        }
        _validate_no_runtime_leak(manifest, temporary_root)
        return manifest


def render_manifest(manifest: dict[str, Any]) -> str:
    return _canonical_json(manifest, pretty=True)


def _sql_string(value: str, *, unicode: bool = False) -> str:
    prefix = "N" if unicode else ""
    return f"{prefix}'{value.replace(chr(39), chr(39) * 2)}'"


def _sql_nullable_json(value: Any) -> str:
    if value is None:
        return "NULL"
    return _sql_string(_canonical_json(value, pretty=False), unicode=True)


def _render_seed_values(manifest: dict[str, Any], indent: str = "    ") -> str:
    rows: list[str] = []
    for entry in manifest["tools"]:
        fields = (
            _sql_string(entry["toolId"]),
            _sql_string(entry["toolName"], unicode=True),
            _sql_string(entry["description"], unicode=True),
            _sql_string(entry["functionName"]),
            _sql_string(entry["toolType"]),
            _sql_string(entry["toolGroup"]),
            _sql_string(entry["descriptionForLLM"], unicode=True),
            _sql_nullable_json(entry["inputSchema"]),
            _sql_nullable_json(entry["outputSchema"]),
            str(int(entry["isReadOnly"])),
            str(int(entry["requireApproval"])),
            str(int(entry["isSystem"])),
            str(int(entry["disabled"])),
            str(int(entry["isCommon"])),
        )
        rows.append(f"{indent}({', '.join(fields)})")
    return ",\n".join(rows)


def _tool_seed_declaration(manifest: dict[str, Any]) -> str:
    return f"""DECLARE @ToolSeed TABLE
(
    ToolID varchar(40) NOT NULL PRIMARY KEY,
    ToolName nvarchar(150) NOT NULL,
    [Description] nvarchar(500) NOT NULL,
    FunctionName varchar(200) NOT NULL UNIQUE,
    ToolType varchar(30) NOT NULL,
    ToolGroup varchar(50) NOT NULL,
    DescriptionForLLM nvarchar(MAX) NOT NULL,
    InputSchemaJson nvarchar(MAX) NOT NULL,
    OutputSchemaJson nvarchar(MAX) NULL,
    IsReadOnly tinyint NOT NULL,
    RequireApproval tinyint NOT NULL,
    IsSystem tinyint NOT NULL,
    Disabled tinyint NOT NULL,
    IsCommon tinyint NOT NULL
);

INSERT INTO @ToolSeed
(
    ToolID, ToolName, [Description], FunctionName, ToolType, ToolGroup,
    DescriptionForLLM, InputSchemaJson, OutputSchemaJson, IsReadOnly,
    RequireApproval, IsSystem, Disabled, IsCommon
)
VALUES
{_render_seed_values(manifest)};
"""


def render_seed_sql(manifest: dict[str, Any]) -> str:
    declaration = _tool_seed_declaration(manifest)
    return f"""-- <Summary>
---- GENERATED ERPX ON P0 assignable Tool Catalog seed.
---- Source: 03.AI ERPX/scripts/export_erpx_assignable_tools.py
---- Runtime schema API: LocalWorkspace.list_tools() + RegisteredTool.get_tool_schema()
---- Do not hand-edit generated rows or JSON Schema.
---- Apply as UTF-8, for example: sqlcmd -f 65001 -b -i 03_ONT1020-ONT1021_Data.sql

SET NOCOUNT ON;
SET XACT_ABORT ON;

IF OBJECT_ID(N'dbo.ONT1020', N'U') IS NULL
    THROW 51100, N'ONT1020 must exist before applying Tool Catalog seed.', 1;

{declaration}
IF (SELECT COUNT(*) FROM @ToolSeed) <> 6
    THROW 51101, N'Generated Tool Catalog must contain exactly six rows.', 1;

IF EXISTS
(
    SELECT 1
    FROM dbo.ONT1020 AS Existing
    WHERE NOT EXISTS
    (
        SELECT 1 FROM @ToolSeed AS Source
        WHERE Source.ToolID = Existing.ToolID
    )
)
    THROW 51102, N'ONT1020 contains noncanonical rows. Review dbo.ONT1020 manually before reapplying this seed.', 1;

IF EXISTS
(
    SELECT 1
    FROM @ToolSeed AS Source
    INNER JOIN dbo.ONT1020 AS Existing
        ON Existing.FunctionName = Source.FunctionName
       AND Existing.ToolID <> Source.ToolID
)
    THROW 51103, N'FunctionName belongs to a different ToolID.', 1;

UPDATE Target
SET DivisionID = '@@@',
    ToolName = Source.ToolName,
    [Description] = Source.[Description],
    FunctionName = Source.FunctionName,
    ToolType = Source.ToolType,
    ToolGroup = Source.ToolGroup,
    DescriptionForLLM = Source.DescriptionForLLM,
    InputSchemaJson = Source.InputSchemaJson,
    OutputSchemaJson = Source.OutputSchemaJson,
    IsReadOnly = Source.IsReadOnly,
    RequireApproval = Source.RequireApproval,
    IsSystem = Source.IsSystem,
    Disabled = Source.Disabled,
    IsCommon = Source.IsCommon,
    LastModifyUserID = 'ASOFT',
    LastModifyDate = GETDATE()
FROM dbo.ONT1020 AS Target
INNER JOIN @ToolSeed AS Source ON Source.ToolID = Target.ToolID
WHERE Target.DivisionID <> '@@@'
   OR Target.ToolName <> Source.ToolName
   OR Target.[Description] <> Source.[Description]
   OR Target.FunctionName <> Source.FunctionName
   OR Target.ToolType <> Source.ToolType
   OR Target.ToolGroup <> Source.ToolGroup
   OR Target.DescriptionForLLM <> Source.DescriptionForLLM
   OR Target.InputSchemaJson <> Source.InputSchemaJson
   OR ISNULL(Target.OutputSchemaJson, N'') <> ISNULL(Source.OutputSchemaJson, N'')
   OR Target.IsReadOnly <> Source.IsReadOnly
   OR Target.RequireApproval <> Source.RequireApproval
   OR Target.IsSystem <> Source.IsSystem
   OR Target.Disabled <> Source.Disabled
   OR Target.IsCommon <> Source.IsCommon;

INSERT INTO dbo.ONT1020
(
    APK, DivisionID, ToolID, ToolName, [Description], FunctionName,
    ToolType, ToolGroup, DescriptionForLLM, InputSchemaJson,
    OutputSchemaJson, IsReadOnly, RequireApproval, IsSystem, Disabled,
    IsCommon, CreateUserID, CreateDate, LastModifyUserID, LastModifyDate
)
SELECT
    NEWID(), '@@@', Source.ToolID, Source.ToolName, Source.[Description],
    Source.FunctionName, Source.ToolType, Source.ToolGroup,
    Source.DescriptionForLLM, Source.InputSchemaJson, Source.OutputSchemaJson,
    Source.IsReadOnly, Source.RequireApproval, Source.IsSystem,
    Source.Disabled, Source.IsCommon, 'ASOFT', GETDATE(), 'ASOFT', GETDATE()
FROM @ToolSeed AS Source
WHERE NOT EXISTS
(
    SELECT 1 FROM dbo.ONT1020 AS Existing
    WHERE Existing.ToolID = Source.ToolID
);

IF (SELECT COUNT(*) FROM dbo.ONT1020) <> 6
    THROW 51104, N'Canonical Tool Catalog validation failed.', 1;
GO
"""


def generated_artifacts(manifest: dict[str, Any]) -> dict[Path, str]:
    return {
        MANIFEST_PATH: render_manifest(manifest),
        SEED_PATH: render_seed_sql(manifest),
    }


def _write_artifacts(artifacts: dict[Path, str]) -> None:
    for path, content in artifacts.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        print(f"wrote {path}")


def _check_artifacts(artifacts: dict[Path, str]) -> int:
    mismatches: list[str] = []
    for path, expected in artifacts.items():
        actual = path.read_text(encoding="utf-8") if path.exists() else None
        if actual != expected:
            mismatches.append(str(path))
    if mismatches:
        print("Generated ERPX Tool artifacts are stale:", file=sys.stderr)
        for path in mismatches:
            print(f"  {path}", file=sys.stderr)
        return 1
    print("Generated ERPX Tool artifacts are current.")
    return 0


async def _main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()

    manifest = await build_manifest()
    artifacts = generated_artifacts(manifest)
    if args.write:
        _write_artifacts(artifacts)
        return 0
    if args.check:
        return _check_artifacts(artifacts)
    print(render_manifest(manifest), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
