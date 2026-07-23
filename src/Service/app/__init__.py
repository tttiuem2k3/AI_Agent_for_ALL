# -*- coding: utf-8 -*-
"""The FastAPI based agent service module, which contains all service-related
components and a configurable FastAPI app factory.
"""

from ._app import create_app
from ._manager import (
    BackgroundTaskManager,
    CancelDispatcher,
    ChatRunRegistry,
    SchedulerManager,
    WakeupDispatcher,
)
from ._tools import (
    AgentCreate,
    DEFAULT_SUB_AGENT_TEMPLATE,
    TeamCreate,
    TeamDelete,
    TeamSay,
)
from ._types import SubAgentTemplate
from .message_bus import (
    InMemoryMessageBus,
    MessageBus,
    MessageBusKeys,
    RedisMessageBus,
)

__all__ = [
    "AgentCreate",
    "BackgroundTaskManager",
    "CancelDispatcher",
    "ChatRunRegistry",
    "DEFAULT_SUB_AGENT_TEMPLATE",
    "InMemoryMessageBus",
    "MessageBus",
    "MessageBusKeys",
    "RedisMessageBus",
    "SchedulerManager",
    "create_app",
    "SubAgentTemplate",
    "TeamCreate",
    "TeamDelete",
    "TeamSay",
    "WakeupDispatcher",
]
