# Standalone ERPX AI host

The standalone host composes FastAPI with Redis-backed durable storage,
Redis-backed live messaging, and local workspaces.

Configure it through environment variables. Secrets must be injected by the
process manager and must not be committed to source control.

```powershell
$env:ASOFT_AI_HOST = "0.0.0.0"
$env:ASOFT_AI_PORT = "8000"
$env:ASOFT_AI_REDIS_HOST = "redis-host"
$env:ASOFT_AI_REDIS_PORT = "6379"
$env:ASOFT_AI_REDIS_USERNAME = "default"
$env:ASOFT_AI_REDIS_PASSWORD = "<secret>"
$env:ASOFT_AI_REDIS_DATABASE = "0"
$env:ASOFT_AI_REDIS_SSL = "false"
$env:ASOFT_AI_WORKSPACE_DIR = "D:\\ASOFT_AI\\workspaces"
$env:ASOFT_ERPX_SQL_CONNECTION_STRING = "<injected ERPX connection string>"
$env:ASOFT_SERVICES_API_KEY = "<existing SERVICES api-key>"

uv sync --extra service --extra storage --extra models --extra mem0
uv run python service/main.py
```

The targeted install above is sufficient for the ERPX chat host and avoids
the development-only `tools` extra. On Windows, `--all-extras` also builds the
Python `ripgrep` package and therefore requires the MSVC linker toolchain.

`ASOFT_AI_REDIS_STORAGE_DB` and `ASOFT_AI_REDIS_BUS_DB` can override the
shared database independently. When omitted, both use
`ASOFT_AI_REDIS_DATABASE`.

When both ERPX SQL and SERVICES api-key settings are present, the host reads
only `ST2101.MainAPIURL/MainAPIPort` to resolve the SERVICES origin used by
dynamic tools. The connection string and api-key are never model-visible and
must be injected by the process manager.

Operational probes:

- `GET /health/live` confirms that the process is alive.
- `GET /health/ready` confirms that Redis is reachable with the configured
  credentials.
- `GET /docs` exposes the FastAPI OpenAPI UI.

The ERPX connection registry (`ONT1000`/`ONT1001`) is the administrative
source of configuration, but it does not inject environment variables into
this process. Deployment must map the approved registry values to these
environment variables.
