# -*- coding: utf-8 -*-
"""AgentScope v2.0.6 memory middleware compatibility tests."""
import asyncio
import sys

import pytest


def test_memory_middlewares_import_without_optional_packages() -> None:
    import Runtime.middleware as middleware

    assert hasattr(middleware, "Mem0Middleware")
    assert hasattr(middleware, "ReMeMiddleware")


def test_reme_dependency_is_loaded_lazily(monkeypatch) -> None:
    from Runtime.middleware import ReMeMiddleware

    monkeypatch.setitem(sys.modules, "reme", None)
    middleware = ReMeMiddleware()

    with pytest.raises(ImportError, match="memory-reme"):
        middleware._build_app()


def test_reme_static_mode_has_no_agent_tool() -> None:
    from Runtime.middleware import ReMeMiddleware

    middleware = ReMeMiddleware(
        parameters=ReMeMiddleware.Parameters(mode="static_control"),
    )

    assert asyncio.run(middleware.list_tools()) == []


def test_reme_default_workspace_is_under_service_workspaces() -> None:
    from Runtime.middleware import ReMeMiddleware

    middleware = ReMeMiddleware()

    assert "service" in middleware.workspace_dir.parts
    assert "workspaces" in middleware.workspace_dir.parts
