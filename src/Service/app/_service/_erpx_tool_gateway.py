# -*- coding: utf-8 -*-
"""Python client/factory for the curated ERPX SERVICES Tool Gateway."""
from typing import Any

import httpx

from Capabilities.tool import ERPXDynamicTool, ERPXExternalTool, ToolBase
from ..storage import CapabilityManifestV2, StorageBase


class ERPXToolGatewayClient:
    """Call one fixed Tool Gateway endpoint with server-managed identity."""

    _EXECUTE_PATH = "/api/v2.0/ON/ToolGateway/execute"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not base_url.strip() or not api_key:
            raise ValueError(
                "ERPX Tool Gateway URL and SERVICES api-key are required.",
            )
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = httpx.Timeout(
            timeout_seconds,
            connect=min(timeout_seconds, 10.0),
        )
        self._transport = transport

    async def execute(
        self,
        tool_id: str,
        runtime_tool_call_id: str,
        run_id: str,
        session_id: str,
        execution_mode: str,
        runtime_subject_id: str | None,
        agent_apk: str | None,
        user_id: str,
        division_id: str,
        capability_hash: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute without accepting model-controlled transport properties."""
        payload = {
            "tool_id": tool_id,
            "runtime_tool_call_id": runtime_tool_call_id,
            "run_id": run_id,
            "session_id": session_id,
            "execution_mode": execution_mode,
            "runtime_subject_id": runtime_subject_id,
            "agent_apk": agent_apk,
            "user_id": user_id,
            "division_id": division_id,
            "capability_hash": capability_hash,
            "arguments": arguments,
        }
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            follow_redirects=False,
            transport=self._transport,
        ) as client:
            response = await client.post(
                self._EXECUTE_PATH,
                json=payload,
                headers={"api-key": self._api_key},
            )
        if response.is_error:
            raise RuntimeError(
                f"ERPX Tool Gateway rejected '{tool_id}' "
                f"with status {response.status_code}.",
            )
        try:
            result = response.json()
        except ValueError as exc:
            raise RuntimeError(
                "ERPX Tool Gateway returned an invalid JSON response.",
            ) from exc
        if not isinstance(result, dict) or result.get("status") != "Succeeded":
            raise RuntimeError(
                f"ERPX Tool Gateway did not complete '{tool_id}'.",
            )
        return result


class ERPXToolFactory:
    """Create one dynamic instance for each effective ServicesApi tool."""

    def __init__(
        self,
        storage: StorageBase,
        client: ERPXToolGatewayClient | None,
    ) -> None:
        self._storage = storage
        self._client = client

    async def __call__(
        self,
        user_id: str,
        agent_id: str | None,
        session_id: str,
    ) -> list[ToolBase]:
        session = await self._storage.get_session(
            user_id,
            agent_id,
            session_id,
        )
        if session is None:
            raise ValueError("ERPX Tool factory cannot resolve the session.")
        manifest = session.config.effective_capabilities
        if manifest is None:
            return []

        # Tools ON executes itself. They surface to the model but never run
        # here, so they need neither a gateway client nor a ToolType allowlist —
        # the executor plane is ON's decision, carried in ``executor_type``.
        external = [tool for tool in manifest.tools if tool.is_external_execution]
        # Tools the runtime still calls in-process through the curated gateway.
        # This is the legacy chat path and stays restricted to ``ServicesApi``:
        # nothing else has ever had a working in-process executor.
        dynamic = [
            tool
            for tool in manifest.tools
            if not tool.is_external_execution and tool.tool_type != "Builtin"
        ]
        unsupported = [
            tool.tool_type
            for tool in dynamic
            if tool.tool_type != "ServicesApi"
        ]
        if unsupported:
            raise ValueError(
                "Unsupported ERPX runtime ToolType in effective capabilities.",
            )

        external_tools: list[ToolBase] = [
            ERPXExternalTool(
                tool_id=tool.tool_id,
                name=tool.function_name,
                description=tool.description_for_llm,
                input_schema=tool.input_schema,
                output_schema=tool.output_schema,
                is_read_only=tool.is_read_only,
                require_approval=tool.require_approval,
            )
            for tool in external
        ]

        if not dynamic:
            return external_tools
        if self._client is None:
            raise ValueError("ERPX Tool Gateway is not configured.")
        direct_model = isinstance(manifest, CapabilityManifestV2)
        manifest_user_id = manifest.user_id
        manifest_division_id = manifest.division_id
        agent_apk = None if direct_model else manifest.agent_apk
        runtime_subject_id = (
            manifest.subject_id if direct_model else None
        )
        capability_hash = (
            manifest.hash if direct_model else manifest.capability_hash
        )
        if (
            (not direct_model and not agent_apk)
            or not manifest_user_id
            or not session.config.runtime_run_id
        ):
            raise ValueError(
                "ERPX dynamic tools require a runtime identity, ERP UserID, "
                "and a trusted RunID.",
            )

        return external_tools + [
            ERPXDynamicTool(
                tool_id=tool.tool_id,
                name=tool.function_name,
                description=tool.description_for_llm,
                input_schema=tool.input_schema,
                output_schema=tool.output_schema,
                is_read_only=tool.is_read_only,
                require_approval=tool.require_approval,
                user_id=manifest_user_id,
                division_id=manifest_division_id,
                execution_mode="DirectModel" if direct_model else "Agent",
                runtime_subject_id=runtime_subject_id,
                agent_apk=agent_apk,
                session_id=session_id,
                run_id=session.config.runtime_run_id,
                capability_hash=capability_hash,
                execute=self._client.execute,
            )
            for tool in dynamic
        ]
