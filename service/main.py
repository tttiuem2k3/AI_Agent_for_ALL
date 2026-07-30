# -*- coding: utf-8 -*-
"""Standalone ASOFT AI Services host for ERPX integration."""

from dataclasses import dataclass
import os
from pathlib import Path

from fastapi import HTTPException
import uvicorn

from Service.app import RedisMessageBus, create_app
from Service.app._service import ERPXToolFactory, ERPXToolGatewayClient
from Service.app._service._erpx_services_config import (
    resolve_services_base_url,
)
from Service.app.storage import RedisStorage
from Service.app.workspace_manager import LocalWorkspaceManager


def _env_int(name: str, default: int, *, minimum: int = 0) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc
    if value < minimum:
        raise RuntimeError(f"{name} must be greater than or equal to {minimum}.")
    return value


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be true or false.")


@dataclass(frozen=True, slots=True)
class ServiceHostSettings:
    """Environment-backed settings for the standalone host."""

    host: str
    port: int
    redis_host: str
    redis_port: int
    redis_username: str | None
    redis_password: str | None
    redis_storage_db: int
    redis_bus_db: int
    redis_ssl: bool
    workspace_dir: Path
    erpx_sql_connection_string: str | None
    services_api_key: str | None

    @classmethod
    def from_env(cls) -> "ServiceHostSettings":
        shared_db = _env_int("ASOFT_AI_REDIS_DATABASE", 0)
        return cls(
            host=os.getenv("ASOFT_AI_HOST", "0.0.0.0").strip(),
            port=_env_int("ASOFT_AI_PORT", 8000, minimum=1),
            redis_host=os.getenv("ASOFT_AI_REDIS_HOST", "localhost").strip(),
            redis_port=_env_int("ASOFT_AI_REDIS_PORT", 6379, minimum=1),
            redis_username=os.getenv("ASOFT_AI_REDIS_USERNAME") or None,
            redis_password=os.getenv("ASOFT_AI_REDIS_PASSWORD") or None,
            redis_storage_db=_env_int(
                "ASOFT_AI_REDIS_STORAGE_DB",
                shared_db,
            ),
            redis_bus_db=_env_int("ASOFT_AI_REDIS_BUS_DB", shared_db),
            redis_ssl=_env_bool("ASOFT_AI_REDIS_SSL"),
            workspace_dir=Path(
                os.getenv("ASOFT_AI_WORKSPACE_DIR", "./data/workspaces"),
            ).resolve(),
            erpx_sql_connection_string=(
                os.getenv(
                    "ASOFT_ERPX_SQL_CONNECTION_STRING",
                    "",
                ).strip() or None
            ),
            services_api_key=(
                os.getenv("ASOFT_SERVICES_API_KEY", "") or None
            ),
        )

    def redis_kwargs(self) -> dict[str, object]:
        kwargs: dict[str, object] = {
            "username": self.redis_username,
            "socket_connect_timeout": 5,
            "socket_timeout": 30,
            "health_check_interval": 30,
        }
        # RedisStorage/RedisMessageBus build ConnectionPool directly. For the
        # current non-TLS deployment no connection-class override is needed.
        if self.redis_ssl:
            from redis.asyncio import SSLConnection

            kwargs["connection_class"] = SSLConnection
        return kwargs


settings = ServiceHostSettings.from_env()
if bool(settings.erpx_sql_connection_string) != bool(
    settings.services_api_key,
):
    raise RuntimeError(
        "ASOFT_ERPX_SQL_CONNECTION_STRING and "
        "ASOFT_SERVICES_API_KEY must be configured together.",
    )
settings.workspace_dir.mkdir(parents=True, exist_ok=True)

redis_kwargs = settings.redis_kwargs()
storage = RedisStorage(
    host=settings.redis_host,
    port=settings.redis_port,
    db=settings.redis_storage_db,
    password=settings.redis_password,
    **redis_kwargs,
)
tool_gateway_client = (
    ERPXToolGatewayClient(
        base_url=resolve_services_base_url(
            settings.erpx_sql_connection_string,
        ),
        api_key=settings.services_api_key,
    )
    if settings.erpx_sql_connection_string and settings.services_api_key
    else None
)
app = create_app(
    storage=storage,
    message_bus=RedisMessageBus(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_bus_db,
        password=settings.redis_password,
        **redis_kwargs,
    ),
    workspace_manager=LocalWorkspaceManager(str(settings.workspace_dir)),
    extra_agent_tools=ERPXToolFactory(storage, tool_gateway_client),
)


@app.get("/health/live", tags=["Health"])
async def live() -> dict[str, str]:
    """Process liveness probe."""
    return {"status": "ok"}


@app.get("/health/ready", tags=["Health"])
async def ready() -> dict[str, str]:
    """Readiness probe that verifies the configured Redis endpoint."""
    from redis.asyncio import Redis

    client = Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_storage_db,
        username=settings.redis_username,
        password=settings.redis_password,
        ssl=settings.redis_ssl,
        socket_connect_timeout=5,
        decode_responses=True,
    )
    try:
        if not await client.ping():
            raise HTTPException(status_code=503, detail="Redis is unavailable.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Redis is unavailable.",
        ) from exc
    finally:
        await client.aclose()
    return {"status": "ready"}


if __name__ == "__main__":
    uvicorn.run(app, host=settings.host, port=settings.port)
