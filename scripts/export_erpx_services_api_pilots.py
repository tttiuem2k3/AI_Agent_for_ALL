# -*- coding: utf-8 -*-
"""Generate the two curated ERPX ServicesApi pilot catalog rows."""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from Capabilities.tool import ERPXDynamicTool, RegisteredTool  # noqa: E402


OUTPUT_PATH = (
    REPOSITORY_ROOT.parent
    / "04.FIXS"
    / "04.ERPX"
    / "7.DATA_MASTER_ERPX"
    / "03_ONT1020_ServicesApi_Pilots.sql"
)


async def _never_execute(*_args: Any) -> dict[str, Any]:
    raise RuntimeError("Schema export must not execute a Tool Gateway call.")


PILOTS = (
    {
        "tool_id": "ON_CHAT_LIST_CONVERSATIONS",
        "function_name": "list_chat_conversations",
        "tool_name": "Liệt kê hội thoại",
        "display_description": (
            "Liệt kê các hội thoại ON chưa lưu trữ của người dùng hiện tại."
        ),
        "description": (
            "List non-archived ON chat conversations owned by the current "
            "user in the current division."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "array",
            "items": {"type": "object"},
        },
        "is_read_only": True,
        "require_approval": False,
    },
    {
        "tool_id": "ON_CHAT_ARCHIVE_CONVERSATION",
        "function_name": "archive_chat_conversation",
        "tool_name": "Lưu trữ hội thoại",
        "display_description": (
            "Lưu trữ một hội thoại ON đã dừng của người dùng hiện tại."
        ),
        "description": (
            "Archive one stopped ON chat conversation owned by the current "
            "user in the current division."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "conversation_id": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 40,
                    "description": "ConversationID to archive.",
                },
            },
            "required": ["conversation_id"],
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "conversation_id": {"type": "string"},
            },
            "required": ["conversation_id"],
        },
        "is_read_only": False,
        "require_approval": True,
    },
)


def _sql(value: str) -> str:
    return "N'" + value.replace("'", "''") + "'"


async def render() -> str:
    rows = []
    for item in sorted(PILOTS, key=lambda value: value["tool_id"]):
        tool = ERPXDynamicTool(
            tool_id=item["tool_id"],
            name=item["function_name"],
            description=item["description"],
            input_schema=item["input_schema"],
            output_schema=item["output_schema"],
            is_read_only=item["is_read_only"],
            require_approval=item["require_approval"],
            user_id="schema-export",
            division_id="schema-export",
            agent_apk="schema-export",
            session_id="schema-export",
            run_id="schema-export",
            capability_hash="0" * 64,
            execute=_never_execute,
        )
        schema = RegisteredTool(tool).get_tool_schema()["function"]
        input_json = json.dumps(
            schema["parameters"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        output_json = json.dumps(
            item["output_schema"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        rows.append(
            "("
            + ",".join(
                (
                    _sql(item["tool_id"]),
                    _sql(item["function_name"]),
                    _sql(item["tool_name"]),
                    _sql(item["display_description"]),
                    _sql(item["description"]),
                    _sql("ServicesApi"),
                    _sql("Productivity"),
                    _sql(input_json),
                    _sql(output_json),
                    "CONVERT(tinyint,"
                    + ("1" if item["is_read_only"] else "0")
                    + ")",
                    "CONVERT(tinyint,"
                    + ("1" if item["require_approval"] else "0")
                    + ")",
                )
            )
            + ")"
        )

    values = ",\n".join(rows)
    return f"""---- GENERATED ServicesApi pilot rows. Run with sqlcmd -f 65001.
---- Source: scripts/export_erpx_services_api_pilots.py
---- This script grants no Agent assignment and performs no DELETE.
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF OBJECT_ID(N'dbo.ONT1020', N'U') IS NULL
    THROW 51300, N'ONT1020 must exist before applying ServicesApi pilots.', 1;

DECLARE @Pilot TABLE
(
    ToolID varchar(50) NOT NULL PRIMARY KEY,
    FunctionName varchar(100) NOT NULL,
    ToolName nvarchar(250) NOT NULL,
    Description nvarchar(500) NOT NULL,
    DescriptionForLLM nvarchar(max) NOT NULL,
    ToolType varchar(30) NOT NULL,
    ToolGroup varchar(50) NOT NULL,
    InputSchemaJson nvarchar(max) NOT NULL,
    OutputSchemaJson nvarchar(max) NOT NULL,
    IsReadOnly tinyint NOT NULL,
    RequireApproval tinyint NOT NULL
);

INSERT @Pilot
(ToolID,FunctionName,ToolName,Description,DescriptionForLLM,ToolType,ToolGroup,
 InputSchemaJson,OutputSchemaJson,IsReadOnly,RequireApproval)
VALUES
{values};

MERGE dbo.ONT1020 AS Target
USING @Pilot AS Source ON Source.ToolID=Target.ToolID
WHEN MATCHED THEN UPDATE SET
    FunctionName=Source.FunctionName,
    ToolName=Source.ToolName,
    Description=Source.Description,
    DescriptionForLLM=Source.DescriptionForLLM,
    ToolType=Source.ToolType,
    ToolGroup=Source.ToolGroup,
    InputSchemaJson=Source.InputSchemaJson,
    OutputSchemaJson=Source.OutputSchemaJson,
    IsReadOnly=Source.IsReadOnly,
    RequireApproval=Source.RequireApproval,
    Disabled=CONVERT(tinyint,0),
    IsCommon=CONVERT(tinyint,1),
    LastModifyDate=GETDATE()
WHEN NOT MATCHED THEN INSERT
(APK,DivisionID,ToolID,FunctionName,ToolName,Description,DescriptionForLLM,ToolType,
 ToolGroup,InputSchemaJson,OutputSchemaJson,IsReadOnly,RequireApproval,
 IsSystem,Disabled,IsCommon,CreateDate)
VALUES
(NEWID(),'@@@',Source.ToolID,Source.FunctionName,Source.ToolName,
 Source.Description,Source.DescriptionForLLM,Source.ToolType,Source.ToolGroup,
 Source.InputSchemaJson,Source.OutputSchemaJson,Source.IsReadOnly,
 Source.RequireApproval,CONVERT(tinyint,1),CONVERT(tinyint,0),
 CONVERT(tinyint,1),GETDATE());

IF EXISTS
(
    SELECT 1
    FROM @Pilot P
    LEFT JOIN dbo.ONT1020 T ON T.ToolID=P.ToolID
    WHERE T.ToolID IS NULL OR T.Disabled<>0
      OR T.FunctionName<>P.FunctionName OR T.ToolType<>P.ToolType
      OR T.Description<>P.Description
      OR T.InputSchemaJson<>P.InputSchemaJson
      OR T.IsReadOnly<>P.IsReadOnly
      OR T.RequireApproval<>P.RequireApproval
)
    THROW 51301, N'ServicesApi pilot conformance validation failed.', 1;
"""


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = await render()
    if args.write:
        OUTPUT_PATH.write_text(content, encoding="utf-8", newline="\n")
    if args.check:
        if not OUTPUT_PATH.exists() or OUTPUT_PATH.read_text(
            encoding="utf-8"
        ) != content:
            print("ServicesApi pilot SQL is stale.", file=sys.stderr)
            return 1
    if not args.write and not args.check:
        print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
