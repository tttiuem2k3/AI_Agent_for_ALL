# ASOFT_AI_SERVICES

ASOFT AI Services is the Python AI platform developed by ASOFT for ERPX. It
provides the agent runtime, model integrations, tools, and service APIs needed
to add AI capabilities to the ERPX ecosystem.

The source is organized around these main areas:

- `Runtime`: agents, messages, events, middleware, and runtime state.
- `Providers`: LLM, embedding, OCR, speech, and credential integrations.
- `Capabilities`: reusable tools, MCP, permissions, RAG, workspaces, and document conversion.
- `ASOFT`: ERPX-specific business integrations such as Knowledge Factory.
- `Service`: the FastAPI application, storage, scheduling, and Web UI APIs.
- `Common`: shared types, exceptions, and utilities.

The project requires Python 3.11 or newer. Development uses `uv` 0.12.x;
`pyproject.toml` enforces the supported `uv` range.

## Purpose

- Provide reusable Python AI services for ERPX applications.
- Keep model providers and agent capabilities behind stable ASOFT interfaces.
- Support multi-tenant, multi-session deployments and ERPX integration.
- Allow ERPX-specific storage, authentication, tools, and business workflows to
  be added without coupling them to a model provider.

## Installation

On Windows, install Python 3.11+, `uv` 0.12.x, Git, Rust stable >=1.88, and the
Visual Studio 2022 C++ x64 toolset. The native document converter uses Rust and
Maturin; `uv sync --all-extras` builds it automatically from the local source.

```powershell
cd E:\Asoft\ASOFT_AI_SERVICES
uv sync --all-extras
(Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned) ; (& e:\Asoft\ASOFT_AI_SERVICES\.venv\Scripts\Activate.ps1)
```

The distribution name is `asoft-ai-services`. It installs the top-level Python
packages `Common`, `Providers`, `Capabilities`, `Runtime`, `Service`, and `ASOFT`.

## Document conversion native runtime

`Capabilities.document_conversion` converts supported office/document formats
to normalized Markdown through the private `asoft-document-conversion-native`
PyO3 wheel. Application code imports only the capability API, never `_native`
directly.

To resynchronize the vendored runtime from the maintained clean fork:

```powershell
.venv\Scripts\python.exe src\Capabilities\document_conversion\_vendor\sync_from_fork.py
.venv\Scripts\python.exe src\Capabilities\document_conversion\_vendor\verify_source_parity.py
```

To build/install only the native wheel into the active project environment:

```powershell
.\src\Capabilities\document_conversion\_vendor\build_native.ps1 -Install
```

## Release bundle

The application and native extension are deliberately shipped as two wheels.
The main `asoft-ai-services` wheel excludes `_native` and `_vendor` source.

```powershell
.\scripts\build_release.ps1 -Clean
.\scripts\install_release.ps1 -Python .\.venv\Scripts\python.exe
```

The release bundle contains `asoft_ai_services-*.whl` and the platform-specific
`asoft_document_conversion_native-*.whl`.

## Quick start

```python
import asyncio
import os

from Capabilities.tool import Bash, Edit, Glob, Grep, Read, Toolkit, Write
from Providers.credential import DashScopeCredential
from Providers.modelLLM.model import DashScopeChatModel
from Runtime.agent import Agent
from Runtime.event import EventType
from Runtime.message import UserMsg


async def main() -> None:
    agent = Agent(
        name="Friday",
        system_prompt="You're a helpful assistant named Friday.",
        model=DashScopeChatModel(
            credential=DashScopeCredential(
                api_key=os.environ["DASHSCOPE_API_KEY"],
            ),
            model="qwen3.6-plus",
        ),
        toolkit=Toolkit(
            tools=[Bash(), Grep(), Glob(), Read(), Write(), Edit()],
        ),
    )

    async for event in agent.reply_stream(UserMsg("Tony", "Hi, Friday!")):
        if event.type == EventType.TEXT_BLOCK_DELTA:
            print(event)


asyncio.run(main())
```

## Agent service

The application under `service` provides a FastAPI-based, multi-tenant and
multi-session agent service:

```bash
uv sync --extra service --extra storage --extra models --extra mem0
uv run python service/main.py
```

The backend listens on `http://localhost:8000` by default and requires Redis.
See [service/README.md](service/README.md) for the complete setup.

## Web UI

Run the companion interface in another terminal:

```bash
cd development/Web_UI_test
pnpm install
pnpm dev
```

Detailed setup and architecture documentation:

- [Setup guide](docs/huong_dan_cai_dat.md)
- [Project architecture](docs/kien_truc_du_an.md)
- [Document conversion native runtime](docs/document_conversion_native.md)
- [AI Service API and Postman examples](docs/Thong_tin_API_ASOFT_AI_SERVICES.md)

## License

Licensed under the Apache License 2.0.
