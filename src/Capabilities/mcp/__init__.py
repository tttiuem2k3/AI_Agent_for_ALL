# -*- coding: utf-8 -*-
"""The MCP module in ASOFT AI Services, that provides fine-grained control over
the MCP servers."""

from ._config import StdioMCPConfig, HttpMCPConfig
from ._mcp_client import MCPClient


__all__ = [
    "MCPClient",
    "StdioMCPConfig",
    "HttpMCPConfig",
]
