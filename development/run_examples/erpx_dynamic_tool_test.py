# -*- coding: utf-8 -*-
"""Targeted tests for schema-driven ERPX Tool Gateway binding."""
import json
from unittest import IsolatedAsyncioTestCase

import httpx

from Capabilities.permission import PermissionBehavior, PermissionContext
from Capabilities.tool import ERPXDynamicTool, RegisteredTool, Toolkit
from Runtime.message import ToolCallBlock
from Runtime.state import AgentState
from Service.app._service import ERPXToolFactory, ERPXToolGatewayClient
from Service.app._service._erpx_services_config import (
    _as_pyodbc_connection_string,
    build_services_base_url,
    resolve_services_base_url,
)
from Service.app.storage import (
    CapabilityManifest,
    SessionConfig,
    SessionRecord,
    ToolCapability,
)
from scripts.export_erpx_services_api_pilots import OUTPUT_PATH, render


def _tool(execute) -> ERPXDynamicTool:
    return ERPXDynamicTool(
        tool_id="API_READ",
        name="read_api",
        description="Read ERPX data.",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        output_schema={"type": "object"},
        is_read_only=True,
        require_approval=False,
        user_id="u",
        division_id="d",
        agent_apk="agent-apk",
        session_id="session",
        run_id="run",
        capability_hash="a" * 64,
        execute=execute,
    )


class ERPXDynamicToolTest(IsolatedAsyncioTestCase):
    async def test_schema_contains_only_canonical_arguments(self) -> None:
        async def execute(*_args):
            return {"status": "Succeeded", "data": {}, "message": "ok"}

        schema = RegisteredTool(_tool(execute)).get_tool_schema()
        self.assertEqual(schema["function"]["name"], "read_api")
        self.assertEqual(
            set(schema["function"]["parameters"]["properties"]),
            {"query"},
        )

    async def test_tool_call_id_and_hidden_scope_reach_client(self) -> None:
        captured = None

        async def execute(*args):
            nonlocal captured
            captured = args
            return {
                "status": "Succeeded",
                "execution_id": "execution",
                "data": {"value": 1},
                "message": "ok",
            }

        toolkit = Toolkit(tools=[_tool(execute)])
        results = [
            item
            async for item in toolkit.call_tool(
                ToolCallBlock(
                    id="runtime-call",
                    name="read_api",
                    input=json.dumps({"query": "x"}),
                ),
                AgentState(),
            )
        ]
        self.assertIsNotNone(captured)
        self.assertEqual(captured[0:8], (
            "API_READ",
            "runtime-call",
            "run",
            "session",
            "agent-apk",
            "u",
            "d",
            "a" * 64,
        ))
        self.assertEqual(captured[8], {"query": "x"})
        self.assertEqual(results[-1].metadata["data"], {"value": 1})

    async def test_permission_policy(self) -> None:
        async def execute(*_args):
            return {"status": "Succeeded"}

        decision = await _tool(execute).check_permissions(
            {},
            PermissionContext(),
        )
        self.assertEqual(decision.behavior, PermissionBehavior.ALLOW)

    async def test_factory_uses_manifest_erp_user_not_runtime_subject(
        self,
    ) -> None:
        captured = None

        class Storage:
            async def get_session(self, *_args) -> SessionRecord:
                return SessionRecord(
                    user_id="erpx:customer:D1:runtime",
                    agent_id="runtime-agent",
                    config=SessionConfig(
                        workspace_id="workspace",
                        runtime_run_id="run",
                        effective_capabilities=CapabilityManifest(
                            agent_apk="agent-apk",
                            agent_id="AGENT",
                            user_id="ERP_USER",
                            division_id="D1",
                            capability_hash="a" * 64,
                            tools=[
                                ToolCapability(
                                    tool_id="API_READ",
                                    function_name="read_api",
                                    tool_type="ServicesApi",
                                    tool_group="ERPX",
                                    description_for_llm="Read ERPX data.",
                                    input_schema={
                                        "type": "object",
                                        "properties": {
                                            "query": {"type": "string"},
                                        },
                                        "required": ["query"],
                                    },
                                    output_schema={"type": "object"},
                                    is_read_only=True,
                                    require_approval=False,
                                ),
                            ],
                        ),
                    ),
                )

        class Client:
            async def execute(self, *args):
                nonlocal captured
                captured = args
                return {"status": "Succeeded", "data": {}}

        factory = ERPXToolFactory(
            Storage(),  # type: ignore[arg-type]
            Client(),  # type: ignore[arg-type]
        )
        tools = await factory(
            "erpx:customer:D1:runtime",
            "runtime-agent",
            "session",
        )
        toolkit = Toolkit(tools=tools)
        _ = [
            item
            async for item in toolkit.call_tool(
                ToolCallBlock(
                    id="runtime-call",
                    name="read_api",
                    input=json.dumps({"query": "x"}),
                ),
                AgentState(),
            )
        ]

        self.assertIsNotNone(captured)
        self.assertEqual(captured[5], "ERP_USER")


class ERPXToolGatewayClientTest(IsolatedAsyncioTestCase):
    async def test_fixed_endpoint_and_server_managed_header(self) -> None:
        captured: httpx.Request | None = None

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured
            captured = request
            return httpx.Response(
                200,
                json={"status": "Succeeded", "data": {"ok": True}},
            )

        client = ERPXToolGatewayClient(
            base_url="https://services.example",
            api_key="existing-api-key",
            transport=httpx.MockTransport(handler),
        )
        result = await client.execute(
            "API_READ",
            "call",
            "run",
            "session",
            "agent",
            "u",
            "d",
            "a" * 64,
            {"query": "x"},
        )
        self.assertEqual(result["data"], {"ok": True})
        self.assertEqual(
            captured.url.path,
            "/api/v2.0/ON/ToolGateway/execute",
        )
        self.assertEqual(
            captured.headers["api-key"],
            "existing-api-key",
        )
        self.assertNotIn("X-ERPX-Tool-Gateway-Key", captured.headers)
        payload = json.loads(captured.content)
        self.assertNotIn("url", payload["arguments"])
        self.assertNotIn("headers", payload["arguments"])

    async def test_services_url_is_resolved_from_st2101(self) -> None:
        executed_sql = None

        class Cursor:
            def execute(self, sql):
                nonlocal executed_sql
                executed_sql = sql

            def fetchall(self):
                return [
                    ("MainAPIURL", "192.168.88.148"),
                    ("MainAPIPort", "9008"),
                ]

        class Connection:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def cursor(self):
                return Cursor()

        def connect(connection_string, *, timeout):
            self.assertEqual(connection_string, "trusted-connection")
            self.assertEqual(timeout, 10)
            return Connection()

        self.assertEqual(
            resolve_services_base_url(
                "trusted-connection",
                connect=connect,
            ),
            "http://192.168.88.148:9008",
        )
        self.assertIn("ST2101", executed_sql)

    async def test_services_url_rejects_conflicting_port(self) -> None:
        with self.assertRaises(RuntimeError):
            build_services_base_url(
                "https://services.example:443",
                "9008",
            )

    async def test_erpx_ado_connection_string_is_converted_for_pyodbc(
        self,
    ) -> None:
        converted = _as_pyodbc_connection_string(
            (
                r"Server=HOST\SQL2025;Database=ERPX;User ID=runtime;"
                "Password=secret;Trusted_Connection=False;"
                "TrustServerCertificate=True;"
            ),
            ["ODBC Driver 17 for SQL Server"],
        )
        self.assertIn(
            "DRIVER={ODBC Driver 17 for SQL Server};",
            converted,
        )
        self.assertIn(r"SERVER={HOST\SQL2025};", converted)
        self.assertIn("DATABASE={ERPX};", converted)
        self.assertIn("UID={runtime};", converted)
        self.assertIn("PWD={secret};", converted)
        self.assertNotIn("User ID=", converted)


class ERPXServicesApiPilotSeedTest(IsolatedAsyncioTestCase):
    async def test_generated_pilot_sql_is_current(self) -> None:
        self.assertEqual(
            OUTPUT_PATH.read_text(encoding="utf-8"),
            await render(),
        )
