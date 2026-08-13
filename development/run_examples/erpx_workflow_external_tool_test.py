# -*- coding: utf-8 -*-
# pylint: disable=redefined-builtin
import json
from typing import Any
from unittest.async_case import IsolatedAsyncioTestCase

from utils import AnyString, MockModel  # noqa: F401  (AnyString kept for parity)

from Runtime.agent import Agent
from Providers.modelLLM.model import ChatResponse
from Capabilities.tool import ERPXDynamicTool, ERPXExternalTool, Toolkit
from Runtime.event import ExternalExecutionResultEvent
from Runtime.message import (
    TextBlock,
    ToolCallBlock,
    ToolResultBlock,
    ToolResultState,
    UserMsg,
)
from Service.app._service import ERPXToolFactory
from Service.app.storage import (
    CapabilityManifest,
    SessionConfig,
    SessionRecord,
    ToolCapability,
)


def _capability(
    *,
    tool_id: str,
    function_name: str,
    tool_type: str,
    executor_type: str,
    is_external_execution: bool,
) -> ToolCapability:
    return ToolCapability(
        tool_id=tool_id,
        function_name=function_name,
        tool_type=tool_type,
        tool_group="ERPX",
        description_for_llm=f"{function_name} something.",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        output_schema={"type": "object"},
        is_read_only=True,
        require_approval=False,
        executor_type=executor_type,
        is_external_execution=is_external_execution,
    )


class _Storage:
    """Only ``get_session`` is reached by the factory."""

    def __init__(self, tools: list[ToolCapability]) -> None:
        self._tools = tools

    async def get_session(self, *_args: Any) -> SessionRecord:
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
                    tools=self._tools,
                ),
            ),
        )


class _RecordingClient:
    """Fails the test loudly if the in-process gateway path is ever used."""

    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, *args: Any) -> dict:
        self.calls += 1
        return {"status": "Succeeded", "data": {}, "message": "ok"}


async def _build(tools: list[ToolCapability]) -> tuple[list, _RecordingClient]:
    client = _RecordingClient()
    factory = ERPXToolFactory(
        _Storage(tools),  # type: ignore[arg-type]
        client,  # type: ignore[arg-type]
    )
    built = await factory(
        "erpx:customer:D1:runtime",
        "runtime-agent",
        "session",
    )
    return built, client


class ERPXExternalToolFactoryTest(IsolatedAsyncioTestCase):
    async def test_on_controlled_tool_becomes_an_external_tool(self) -> None:
        built, _ = await _build(
            [
                _capability(
                    tool_id="ERPX_OOF2111_CREATE_TASK",
                    function_name="create_task",
                    tool_type="ScreenAction",
                    executor_type="ScreenAction",
                    is_external_execution=True,
                ),
            ],
        )

        tool = built[0]
        self.assertIsInstance(tool, ERPXExternalTool)
        self.assertTrue(tool.is_external_tool)
        self.assertEqual(tool.name, "create_task")
        self.assertEqual(
            set(tool.input_schema["properties"]),
            {"query"},
        )

    async def test_builtin_tool_claiming_external_execution_is_rejected(self) -> None:
        """Mâu thuẫn phải nổ, không được im lặng.

        ``Builtin`` nghĩa là chính runtime Python sở hữu và chạy Tool đó; nó đã
        được nạp từ workspace và lọc theo manifest. Nếu factory lại dựng thêm
        một bản external cho cùng Tool, toolkit có HAI mục trùng tên — model
        thấy một tên, hai hành vi. ``executor_type='PythonRuntime'`` (tức không
        external) là cách ERPX diễn đạt đúng ý này, nên tới được đây là dữ liệu
        đã sai.
        """
        with self.assertRaises(ValueError):
            await _build(
                [
                    _capability(
                        tool_id="ASCOPE_READ",
                        function_name="read_runtime",
                        tool_type="Builtin",
                        executor_type="ScreenAction",
                        is_external_execution=True,
                    ),
                ],
            )

    async def test_legacy_chat_tool_stays_in_process(self) -> None:
        built, _ = await _build(
            [
                _capability(
                    tool_id="API_READ",
                    function_name="read_api",
                    tool_type="ServicesApi",
                    executor_type="ServicesApi",
                    is_external_execution=False,
                ),
            ],
        )

        self.assertIsInstance(built[0], ERPXDynamicTool)
        self.assertFalse(built[0].is_external_tool)

    async def test_non_services_api_tool_type_is_no_longer_rejected(self) -> None:
        """Trước Task 3.2 factory ném cho MỌI tool_type khác ServicesApi.

        Đó chính là chốt chặn khiến mặt phẳng PythonRuntime không thể tồn tại.
        """
        built, _ = await _build(
            [
                _capability(
                    tool_id="ERPX_OOF2111_CREATE_TASK",
                    function_name="create_task",
                    tool_type="ScreenAction",
                    executor_type="ScreenAction",
                    is_external_execution=True,
                ),
            ],
        )

        self.assertEqual(len(built), 1)

    async def test_external_tool_call_is_unreachable(self) -> None:
        built, _ = await _build(
            [
                _capability(
                    tool_id="ERPX_OOF2111_CREATE_TASK",
                    function_name="create_task",
                    tool_type="ScreenAction",
                    executor_type="ScreenAction",
                    is_external_execution=True,
                ),
            ],
        )

        with self.assertRaises(RuntimeError):
            await built[0].call(_runtime_tool_call_id="c1", query="x")


class ToolCapabilityWireContractTest(IsolatedAsyncioTestCase):
    """Ghim tập trường của một Tool trên dây, đối xứng với bản ghim bên ERPX.

    Bản ghim bên kia: ``ASOFT.ON.Gateway.Tests/ONCapabilityManifestWireTests.cs``
    (``ToolPayload_HasExactlyTheFieldsPythonExpects``).  Hợp đồng này không có
    compiler nào kiểm: manifest v2 được tính lại hash NGAY TẠI ĐÂY trên payload
    nhận được, nên chỉ cần một bên thêm hoặc bớt một trường là mọi phiên
    DirectModel chết với "manifest hash does not match" — không có cảnh báo nào
    sớm hơn thời điểm đó.
    """

    async def test_tool_capability_wire_fields_match_erpx(self) -> None:
        capability = _capability(
            tool_id="ASCOPE_READ",
            function_name="read_runtime",
            tool_type="Builtin",
            executor_type="PythonRuntime",
            is_external_execution=True,
        )

        self.assertEqual(
            sorted(capability.model_dump(mode="json").keys()),
            [
                "description_for_llm",
                "executor_type",
                "function_name",
                "input_schema",
                "is_external_execution",
                "is_read_only",
                "output_schema",
                "require_approval",
                "tool_group",
                "tool_id",
                "tool_type",
            ],
        )


class ERPXExternalToolTurnTest(IsolatedAsyncioTestCase):
    """Một lượt Agent thật: dừng lại chờ ON, rồi chạy tiếp khi có kết quả."""

    async def test_turn_pauses_for_on_then_resumes_to_reply_end(self) -> None:
        built, client = await _build(
            [
                _capability(
                    tool_id="ERPX_OOF2111_CREATE_TASK",
                    function_name="create_task",
                    tool_type="ScreenAction",
                    executor_type="ScreenAction",
                    is_external_execution=True,
                ),
            ],
        )

        model = MockModel()
        agent = Agent(
            name="Friday",
            system_prompt="You are a helpful assistant.",
            model=model,
            toolkit=Toolkit(tools=built),
        )
        tool_input = json.dumps({"query": "x"})
        model.set_responses(
            [
                [
                    ChatResponse(
                        content=[
                            ToolCallBlock(
                                id="call-1",
                                name="create_task",
                                input=tool_input,
                            ),
                        ],
                        is_last=False,
                        usage=None,
                    ),
                    ChatResponse(
                        content=[
                            ToolCallBlock(
                                id="call-1",
                                name="create_task",
                                input=tool_input,
                            ),
                        ],
                        is_last=True,
                        usage=None,
                    ),
                ],
                [
                    ChatResponse(
                        content=[TextBlock(text="done")],
                        is_last=False,
                        usage=None,
                    ),
                    ChatResponse(
                        content=[TextBlock(text="done")],
                        is_last=True,
                        usage=None,
                    ),
                ],
            ],
        )

        first = [
            event.type
            async for event in agent.reply_stream(
                UserMsg(name="user", content="Test"),
            )
        ]

        self.assertIn("REQUIRE_EXTERNAL_EXECUTION", first)
        self.assertNotIn("REPLY_END", first)
        # Cốt lõi: ON quyết định, Python không tự gọi ngược HTTP.
        self.assertEqual(client.calls, 0)

        resumed = [
            event.type
            async for event in agent.reply_stream(
                inputs=ExternalExecutionResultEvent(
                    reply_id=agent.state.reply_id,
                    execution_results=[
                        ToolResultBlock(
                            id="call-1",
                            name="create_task",
                            output=[TextBlock(text="ON đã chạy xong.")],
                            state=ToolResultState.SUCCESS,
                        ),
                    ],
                ),
            )
        ]

        self.assertIn("REPLY_END", resumed)
        self.assertEqual(client.calls, 0)
