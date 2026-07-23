# -*- coding: utf-8 -*-
"""Long-term middleware middlewares for ASOFT AI Services agents.

Currently only the mem0 backend is implemented. Import the public class
from the middleware package::

    from Runtime.middleware import Mem0Middleware

Future backends (e.g. dedicated vector stores, custom user-profile
services) can sit alongside ``_mem0/`` under this package and be
re-exported here.
"""

from ._mem0 import Mem0Middleware
from ._mem0._asoft_adapter import (
    ASOFTEmbedding,
    ASOFTLLM,
    _convert_messages_to_asoft,
    _parse_chat_response,
    build_mem0_config,
)

__all__ = [
    "ASOFTEmbedding",
    "ASOFTLLM",
    "Mem0Middleware",
    "_convert_messages_to_asoft",
    "_parse_chat_response",
    "build_mem0_config",
]
