# -*- coding: utf-8 -*-
"""Conformance tests for the generated ERPX assignable Tool Catalog."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from unittest import IsolatedAsyncioTestCase, main

from jsonschema import Draft202012Validator


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts import export_erpx_assignable_tools as exporter  # noqa: E402


SCHEMA_PATH = (
    exporter.CORES_ROOT
    / "01.ERPX"
    / "_ARCHITECTURE"
    / "_DOCS_ON"
    / "contracts"
    / "tool-catalog-manifest-v1.schema.json"
)


class ERPXToolManifestTest(IsolatedAsyncioTestCase):
    """Keep Python schemas, committed manifest, and SQL byte-conformant."""

    async def test_manifest_is_deterministic_and_schema_valid(self) -> None:
        first = await exporter.build_manifest()
        second = await exporter.build_manifest()

        self.assertEqual(first, second)
        self.assertEqual(
            [tool["toolId"] for tool in first["tools"]],
            [
                "ASCOPE_BASH",
                "ASCOPE_EDIT",
                "ASCOPE_GLOB",
                "ASCOPE_GREP",
                "ASCOPE_READ",
                "ASCOPE_WRITE",
            ],
        )
        self.assertEqual(
            {tool["functionName"] for tool in first["tools"]},
            exporter.EXPECTED_FUNCTION_NAMES,
        )

        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(first)

    async def test_committed_artifacts_match_runtime(self) -> None:
        manifest = await exporter.build_manifest()
        for path, expected in exporter.generated_artifacts(manifest).items():
            self.assertTrue(path.exists(), str(path))
            self.assertEqual(path.read_text(encoding="utf-8"), expected, str(path))

    async def test_internal_and_roadmap_tools_are_not_catalogued(self) -> None:
        manifest = await exporter.build_manifest()
        serialized = exporter.render_manifest(manifest)
        seed = exporter.render_seed_sql(manifest)

        for forbidden in (
            "TaskCreate",
            "ToolStop",
            "ScheduleCreate",
            "TeamCreate",
            "reset_tools",
            '"Skill"',
            "search_memory",
            "HttpRequest",
            "QueryERPXData",
        ):
            self.assertNotIn(forbidden, serialized)
            self.assertNotIn(forbidden, seed)

    async def test_schema_contains_runtime_grep_surface(self) -> None:
        manifest = await exporter.build_manifest()
        grep = next(
            tool for tool in manifest["tools"]
            if tool["functionName"] == "Grep"
        )
        properties = grep["inputSchema"]["properties"]
        self.assertEqual(
            {
                "pattern",
                "path",
                "output_mode",
                "glob",
                "type",
                "-A",
                "-B",
                "-C",
                "context",
                "n",
                "i",
                "case_insensitive",
                "multiline",
                "head_limit",
                "offset",
            },
            set(properties),
        )
        self.assertEqual(properties["n"]["default"], True)
        self.assertEqual(properties["head_limit"].get("default"), None)


if __name__ == "__main__":
    main()
