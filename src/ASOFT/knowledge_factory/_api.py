# -*- coding: utf-8 -*-
"""Server-to-server API for ERPX Knowledge Factory publish signals."""
from __future__ import annotations

from contextlib import asynccontextmanager
import hmac

from fastapi import APIRouter, FastAPI, Header, HTTPException, status

from ._errors import KnowledgeFactoryError
from ._models import PublishRequest, PublishResponse
from ._runtime import KnowledgeFactoryRuntime


def _authorize(runtime: KnowledgeFactoryRuntime, provided: str | None) -> None:
    expected = runtime.settings.api_key
    if expected is None:
        return
    if provided is None or not hmac.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Knowledge Factory API key.",
        )


def create_knowledge_factory_router(
    runtime: KnowledgeFactoryRuntime,
    *,
    prefix: str = "/asoft/knowledge-factory",
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=["ASOFT Knowledge Factory"])

    @router.post(
        "/publish",
        response_model=PublishResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def publish(
        request: PublishRequest,
        api_key: str | None = Header(default=None, alias="api-key"),
    ) -> PublishResponse:
        _authorize(runtime, api_key)
        try:
            return await runtime.trigger(request.snapshot_apk)
        except KnowledgeFactoryError as exc:
            raise _as_http_error(exc) from exc

    return router


def create_knowledge_factory_app(
    runtime: KnowledgeFactoryRuntime | None = None,
) -> FastAPI:
    runtime = runtime or KnowledgeFactoryRuntime.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        del app
        async with runtime:
            yield

    app = FastAPI(title="ASOFT Knowledge Factory", lifespan=lifespan)
    app.state.knowledge_factory_runtime = runtime
    app.include_router(create_knowledge_factory_router(runtime))
    return app


def _as_http_error(exc: KnowledgeFactoryError) -> HTTPException:
    if exc.code == "SNAPSHOT_NOT_FOUND":
        code = status.HTTP_404_NOT_FOUND
    elif exc.code in {
        "KNOWLEDGE_FACTORY_DISABLED",
        "KNOWLEDGE_FACTORY_NOT_CONFIGURED",
        "DB_SCHEMA_NOT_READY",
        "SQL_VECTOR_NOT_SUPPORTED",
    }:
        code = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        code = status.HTTP_409_CONFLICT
    return HTTPException(
        status_code=code,
        detail={"code": exc.code, "message": exc.safe_message},
    )
