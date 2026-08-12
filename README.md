# ASOFT_AI_SERVICES

ASOFT AI Services is the Python AI platform developed by ASOFT for ERPX. It
provides the agent runtime, model integrations, tools, and service APIs needed
to add AI capabilities to the ERPX ecosystem.

The source is organized around four main areas:

- `Runtime`: agents, messages, events, middleware, and runtime state.
- `Providers/modelLLM`: LLM chat models and provider-specific formatters.
- `Providers/modelBSN`: specialized embedding, OCR, STT, and TTS models.
- `Providers/credential`: shared provider credentials and connection settings.
- `Capabilities`: tools, MCP, permissions, skills, and workspaces.
- `Service`: the FastAPI application, storage, scheduling, and Web UI APIs.

The project requires Python 3.11 or newer.

## Purpose

- Provide reusable Python AI services for ERPX applications.
- Keep model providers and agent capabilities behind stable ASOFT interfaces.
- Support multi-tenant, multi-session deployments and ERPX integration.
- Allow ERPX-specific storage, authentication, tools, and business workflows to
  be added without coupling them to a model provider.

## Installation

Install the project from source:

```bash
uv sync --all-extras
```

Alternatively, install it in editable mode:

```bash
uv pip install -e ".[full]"
```

The distribution name is `asoft-ai-services`. It installs the top-level Python
packages `Common`, `Providers`, `Capabilities`, `Runtime`, and `Service`.

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
- [AI Service API and Postman examples](docs/Thong_tin_API_ASOFT_AI_SERVICES.md)

## License

Licensed under the Apache License 2.0.
